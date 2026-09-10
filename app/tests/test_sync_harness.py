#!/usr/bin/env python3
"""
E2E sync harness supporting two runtime modes:

MODE=local  -> local backend (default: http://localhost:5000) and Postgres DB
MODE=pa     -> PythonAnywhere backend (default: https://srpihhllc.pythonanywhere.com) and MySQL DB

Environment variables:
- MODE (local|pa)
- BACKEND_URL
- HEALTH_PATH (default: /api/v1/health)
- AUTH_TOKEN
- USER_ID, ACCOUNT_ID
- IDEMPOTENCY_KEY
- POLL_TIMEOUT_SECS, POLL_INTERVAL_SECS

Local-specific:
- DB_DSN OR PG_HOST/PG_PORT/PG_USER/PG_PASSWORD/PG_DB

PythonAnywhere-specific:
- DB_USER/DB_PASSWORD/DB_HOST/DB_PORT/DB_NAME
"""

from __future__ import annotations
import os
import sys
import time
import uuid
import requests
from urllib.parse import urljoin
from datetime import datetime, timezone, timedelta
from dotenv import load_dotenv

# Load environment variables from .env before top-level constants evaluate
load_dotenv()

MODE = os.getenv("MODE", "local").lower()  # "local" or "pa"

# API / token settings (can be overridden)
if MODE == "pa":
    BACKEND_URL = os.getenv(
        "BACKEND_URL", "https://srpihhllc.pythonanywhere.com"
    )
else:
    BACKEND_URL = os.getenv("BACKEND_URL", "http://localhost:5000")

HEALTH_PATH = os.getenv("HEALTH_PATH", "/api/v1/health")
AUTH_TOKEN = os.getenv("AUTH_TOKEN", "test-token")
USER_ID = os.getenv("USER_ID", "c22cf8da-d61b-4450-8ed7-b1fcec5d5799")
ACCOUNT_ID = os.getenv("ACCOUNT_ID", "100000000001")
IDEMPOTENCY_KEY = os.getenv("IDEMPOTENCY_KEY", f"e2e-{uuid.uuid4().hex}")
POLL_TIMEOUT = int(os.getenv("POLL_TIMEOUT_SECS", "120"))
POLL_INTERVAL = int(os.getenv("POLL_INTERVAL_SECS", "3"))

HEADERS = {
    "Authorization": f"Bearer {AUTH_TOKEN}",
    "Content-Type": "application/json",
    "Idempotency-Key": IDEMPOTENCY_KEY,
}


def wait_for_backend(
    health_path: str = HEALTH_PATH, timeout: int = 60, interval: int = 2
) -> None:
    url = urljoin(BACKEND_URL, health_path)
    start = time.time()
    while time.time() - start < timeout:
        try:
            r = requests.get(url, timeout=5)
            if r.status_code >= 100:
                print(f"Backend reachable: {url} (status {r.status_code})")
                return
        except requests.RequestException:
            pass
        time.sleep(interval)
    raise TimeoutError(f"Backend not reachable at {url} after {timeout}s")


def enqueue_sync() -> str:
    url = urljoin(BACKEND_URL, "/api/v1/sync")
    payload = {
        "user_id": USER_ID,
        "accounts": [{"id": ACCOUNT_ID}],
        "trigger": "e2e_test",
        "options": {"full_refresh": True},
    }
    r = requests.post(url, json=payload, headers=HEADERS, timeout=30)
    if not r.ok:
        print(f"🚨 ENQUEUE ERROR ({r.status_code}): {r.text}", file=sys.stderr)
    r.raise_for_status()
    body = r.json()
    data = body.get("data") if isinstance(body.get("data"), dict) else body
    return data.get("job_id") or data.get("id") or str(data)


def poll_job(job_id: str):
    url = urljoin(BACKEND_URL, f"/api/v1/sync/jobs/{job_id}")
    start = time.time()
    while time.time() - start < POLL_TIMEOUT:
        try:
            r = requests.get(
                url,
                headers={"Authorization": f"Bearer {AUTH_TOKEN}"},
                timeout=10,
            )
        except requests.RequestException:
            time.sleep(POLL_INTERVAL)
            continue
        if r.status_code == 404:
            time.sleep(POLL_INTERVAL)
            continue
        if not r.ok:
            print(
                f"🚨 POLL ERROR ({r.status_code}): {r.text}", file=sys.stderr
            )
        r.raise_for_status()
        body = r.json()
        j = body.get("data") if isinstance(body.get("data"), dict) else body
        status = j.get("status")
        if status in ("completed", "success"):
            return j
        if status in ("failed", "error"):
            raise RuntimeError(f"Sync job failed: {j}")
        time.sleep(POLL_INTERVAL)
    raise TimeoutError("Polling sync job timed out")


def get_db_connection():
    if MODE == "pa":
        try:
            import pymysql
            import pymysql.cursors
        except Exception as e:
            raise RuntimeError(
                "pymysql is required for MODE=pa. Install with pip install pymysql"
            ) from e

        DB_USER = os.getenv("DB_USER")
        DB_PASSWORD = os.getenv("DB_PASSWORD")
        DB_HOST = os.getenv("DB_HOST")
        DB_PORT = int(os.getenv("DB_PORT", "3306"))
        DB_NAME = os.getenv("DB_NAME")
        if not all([DB_USER, DB_PASSWORD, DB_HOST, DB_NAME]):
            raise RuntimeError(
                "Missing DB_* env vars for MODE=pa (DB_USER/DB_PASSWORD/DB_HOST/DB_NAME)."
            )
        conn = pymysql.connect(
            host=DB_HOST,
            user=DB_USER,
            password=DB_PASSWORD,
            database=DB_NAME,
            port=DB_PORT,
            cursorclass=pymysql.cursors.DictCursor,
            autocommit=True,
        )
        return conn, "mysql"
    else:
        try:
            import psycopg2
            import psycopg2.extras
        except Exception as e:
            raise RuntimeError(
                "psycopg2-binary is required for MODE=local. Install with pip install psycopg2-binary"
            ) from e

        DB_DSN = os.getenv("DB_DSN")
        if DB_DSN:
            conn = psycopg2.connect(DB_DSN)
            conn.autocommit = True
            return conn, "postgres"
        PG_HOST = os.getenv("PG_HOST", "localhost")
        PG_PORT = int(os.getenv("PG_PORT", "5432"))
        PG_USER = os.getenv("PG_USER", "postgres")
        PG_PASSWORD = os.getenv("PG_PASSWORD", "")
        PG_DB = os.getenv("PG_DB", "postgres")
        conn = psycopg2.connect(
            host=PG_HOST,
            port=PG_PORT,
            user=PG_USER,
            password=PG_PASSWORD,
            dbname=PG_DB,
        )
        conn.autocommit = True
        return conn, "postgres"


def query_db_for_transactions(
    conn, driver: str, account_id: str, lookback_minutes: int = 60
):
    """
    Dynamically inspects table columns to construct a valid query string
    for transactions across both MySQL and Postgres environments.
    """
    threshold = datetime.now(timezone.utc) - timedelta(
        minutes=int(lookback_minutes)
    )

    with conn.cursor() as cur:
        # Dynamically inspect column names for the target database
        if driver == "mysql":
            cur.execute("SHOW COLUMNS FROM transactions;")
            raw_cols = cur.fetchall()
            cols = [
                col["Field"] if isinstance(col, dict) else col[0]
                for col in raw_cols
            ]
        else:
            cur.execute(
                "SELECT column_name FROM information_schema.columns WHERE table_name = 'transactions';"
            )
            raw_cols = cur.fetchall()
            cols = [
                col["column_name"] if isinstance(col, dict) else col[0]
                for col in raw_cols
            ]

        # Determine the correct filter and ordering columns available in the schema
        filter_col = (
            "posted_at"
            if "posted_at" in cols
            else "date"
            if "date" in cols
            else "created_at"
            if "created_at" in cols
            else "timestamp"
            if "timestamp" in cols
            else cols[0]
        )

        order_col = (
            "posted_at"
            if "posted_at" in cols
            else "date"
            if "date" in cols
            else "created_at"
            if "created_at" in cols
            else filter_col
        )

        sql = f"""
            SELECT * FROM transactions
            WHERE account_id = %s AND {filter_col} >= %s
            ORDER BY {order_col} DESC
            LIMIT 100
        """

        cur.execute(sql, (account_id, threshold.strftime("%Y-%m-%d %H:%M:%S")))
        rows = cur.fetchall()

        result = []
        for r in rows:
            if isinstance(r, dict):
                result.append(r)
            else:
                cols_desc = [desc[0] for desc in cur.description]
                result.append(
                    {cols_desc[i]: r[i] for i in range(len(cols_desc))}
                )
        return result


def main():
    print(f"E2E sync harness starting (MODE={MODE})")
    print("Backend URL:", BACKEND_URL)
    try:
        wait_for_backend(timeout=60)
    except TimeoutError as e:
        print("ERROR:", e, file=sys.stderr)
        sys.exit(2)

    print("Enqueueing sync with idempotency key:", IDEMPOTENCY_KEY)
    job_id = enqueue_sync()
    if isinstance(job_id, dict):
        job_id = job_id.get("job_id") or job_id.get("id")
    print("Enqueued job:", job_id)
    print("Polling job status...")
    job = poll_job(job_id)
    print("Job finished:", job.get("status"))

    try:
        conn, driver = get_db_connection()
    except Exception as e:
        print("ERROR connecting to DB:", e, file=sys.stderr)
        sys.exit(3)

    try:
        rows = query_db_for_transactions(conn, driver, ACCOUNT_ID)
        print(f"Found {len(rows)} transactions for account {ACCOUNT_ID}:")
        for r in rows[:10]:
            print(r)
        if len(rows) == 0:
            raise AssertionError("No transactions found after sync")

        # Check posted timestamp consistency if available
        posted_times = [
            r.get("posted_at") or r.get("date")
            for r in rows
            if r.get("posted_at") or r.get("date")
        ]
        if posted_times and len(posted_times) != len(set(posted_times)):
            raise AssertionError("Duplicate posted timestamps found")
    finally:
        try:
            conn.close()
        except Exception:
            pass

    print("E2E sync harness succeeded")


if __name__ == "__main__":
    main()
