Runbook — Sync Worker (minimal) / How to run the harness in MODE=pa

Purpose
- Quick operator guide to start the minimal sync worker, run the E2E harness against PythonAnywhere (MODE=pa), and collect diagnostics.

Safety checklist
- Use a test user/account and a unique Idempotency key.
- Do NOT paste DB passwords or provider secrets into open logs.
- Ensure worker and web app share the same environment variables where required.

Files referenced
- app/workers/sync_worker.py — minimal safe worker entrypoint (BLPOP loop)
- app/workers/__init__.py — package marker / lazy export
- run-worker.sh — helper script to run the minimal worker
- app/tests/test_sync_harness.py — the harness (supports MODE=pa)

Start the minimal worker (foreground)
1. Open a single Bash console (PythonAnywhere: Consoles → Bash).
2. Activate venv (if used):
   cd ~/PlaidBridgeOpenBankingApi
   source venv/bin/activate
3. Export environment variables (example):
   export MODE=pa
   export BACKEND_URL="https://srpihhllc.pythonanywhere.com"
   export HEALTH_PATH="/api/v1/health"
   export DB_USER="srpihhllc"
   export DB_PASSWORD="<YOUR_DB_PASSWORD>"
   export DB_HOST="srpihhllc.mysql.pythonanywhere-services.com"
   export DB_PORT=3306
   export DB_NAME="srpihhllc$default"
   export REDIS_URL="redis://USER:PASS@redis-host:PORT"
4. Start the worker in foreground:
   python -m app.workers.sync_worker
   - Watch the console for logs. Keep this tab open.

Run the harness in MODE=pa (safe)
1. Open a new tab that SHARES the same container (PythonAnywhere: use "Open new tab" from the same Bash console).
2. Ensure venv is active and the same env vars are present.
3. Export test params:
   export MODE=pa
   export BACKEND_URL="https://srpihhllc.pythonanywhere.com"
   export HEALTH_PATH="/api/v1/health"
   export AUTH_TOKEN="<TEST_BEARER_TOKEN>"
   export USER_ID=TEST_USER_ID
   export ACCOUNT_ID="acct_test_pa_1"
   export IDEMPOTENCY_KEY="test-sync-$(date -u +%s)-$RANDOM"
4. Run the harness:
   python app/tests/test_sync_harness.py
   - Harness waits for the health endpoint, enqueues a job, polls for completion, then checks MySQL for results.

Quick curl + SQL checks (copy/paste)
- Enqueue:
  IDEMPOTENCY_KEY="itest-$(date +%s)-$RANDOM"
  curl -sS -X POST "https://srpihhllc.pythonanywhere.com/api/sync" \
    -H "Authorization: Bearer ${AUTH_TOKEN}" \
    -H "Idempotency-Key: ${IDEMPOTENCY_KEY}" \
    -H "Content-Type: application/json" \
    -d '{"user_id": TEST_USER_ID, "accounts":[{"id":"TEST_ACCOUNT_ID"}], "trigger":"manual"}' | jq .

- Poll job:
  curl -sS -H "Authorization: Bearer ${AUTH_TOKEN}" \
    "https://srpihhllc.pythonanywhere.com/api/sync/jobs/JOB_ID" | jq .

- Check MySQL (from PythonAnywhere console):
  mysql -u DB_USER -p -h DB_HOST DB_NAME -e \
  "SELECT id,job_id,status,idempotency_key,created_at,started_at,finished_at FROM sync_jobs WHERE idempotency_key='${IDEMPOTENCY_KEY}';"

  mysql -u DB_USER -p -h DB_HOST DB_NAME -e \
  "SELECT id,account_id,amount,posted_at,inserted_at FROM transactions WHERE account_id='TEST_ACCOUNT_ID' AND inserted_at > NOW() - INTERVAL 120 MINUTE ORDER BY posted_at DESC LIMIT 50;"

Collect artifacts for diagnosis
- Worker console logs (the Bash tab you used to run the worker)
- Web app error log (PythonAnywhere: Web → Error log)
- Outputs of the SQL queries above
- Raw curl responses for enqueue / poll
- Harness output (stdout/stderr)

Troubleshooting tips (common failures)
- ENQUEUE succeeds but job never runs: worker not running, check worker console, check Redis broker connectivity.
- Health endpoint unreachable: verify BACKEND_URL and HEALTH_PATH; curl from a console sharing the same container.
- DB access denied: confirm DB_NAME is exactly the PythonAnywhere name (e.g., srpihhllc$default) and DB credentials are correct.
- Duplicate writes: verify idempotency_key passed and dedupe logic in job handler.

Notes
- The provided minimal worker is a placeholder; replace process_job() with the real processing logic before relying on it for production.
- Keep secrets out of repository. Use PythonAnywhere Web environment or secure storage.

End of runbook.