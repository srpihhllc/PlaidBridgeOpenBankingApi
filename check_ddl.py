import os
import sys
import pathlib
import sqlalchemy as sa

# Make sure we import the application package from PlaidBridgeOpenBankingApi
repo_root = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(repo_root))
sys.path.insert(0, str(repo_root / "PlaidBridgeOpenBankingApi"))

# Prevent Redis background retries and force testing config
os.environ.setdefault("REDIS_URL", "")
os.environ.setdefault("REDIS_STORAGE_URI", "")
os.environ.setdefault("TESTING", "1")

# Import factory the same way the application uses it (top-level 'app' package)
from app import create_app

# create app in testing mode
app = create_app("testing")

# Import db AFTER the app factory to avoid duplicate-table mapping problems
from app.extensions import db

with app.app_context():
    # Ensure a clean in-memory DB for testing paths (create_all is safe here)
    db.create_all()

    # Acquire a Connection the same way tests use it
    conn = db.session.connection()

    # 1) show the CREATE TABLE DDL for bank_transactions
    try:
        row = conn.execute(sa.text(
            "SELECT sql FROM sqlite_master WHERE type='table' AND name='bank_transactions'"
        )).fetchone()
        ddl = row[0] if row else "<no-ddl>"
    except Exception as exc:
        ddl = f"<error retrieving DDL: {exc}>"
    print("==== bank_transactions DDL ====")
    print(ddl)
    print()

    # 2) show PRAGMA foreign_keys for this connection
    try:
        fk_on_row = conn.execute(sa.text("PRAGMA foreign_keys")).fetchone()
        fk_on = fk_on_row[0] if fk_on_row else fk_on_row
    except Exception as exc:
        fk_on = f"<error: {exc}>"
    print("PRAGMA foreign_keys =>", fk_on)
    print()

    # 3) list foreign keys declared on bank_transactions (SQLite pragma)
    try:
        fk_list = conn.execute(sa.text("PRAGMA foreign_key_list('bank_transactions')")).fetchall()
    except Exception as exc:
        fk_list = [("error", str(exc))]
    print("PRAGMA foreign_key_list('bank_transactions') rows:", len(fk_list))
    for fk in fk_list:
        print(fk)
    print()

    # 4) simple sanity: list table names
    try:
        tables = conn.execute(sa.text("SELECT name FROM sqlite_master WHERE type='table'")).fetchall()
        tables_list = [t[0] for t in tables]
    except Exception as exc:
        tables_list = [f"<error: {exc}>"]
    print("Tables:", tables_list)
