#!/usr/bin/env bash
# run-worker.sh - start a foreground minimal worker (use from project root)
set -euo pipefail
. venv/bin/activate || true
export MODE=${MODE:-pa}
export WORKER_SYNC_LIST_KEY=${WORKER_SYNC_LIST_KEY:-sync:jobs}
export WORKER_POLL_INTERVAL=${WORKER_POLL_INTERVAL:-1.0}
python -m app.workers.sync_worker