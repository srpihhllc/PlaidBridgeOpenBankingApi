# /home/srpihhllc/PlaidBridgeOpenBankingApi/app/scripts/cron_purge_zombies.py

import sys
from datetime import datetime
from pathlib import Path

project_root = str(Path(__file__).resolve().parents[2])
if project_root not in sys.path:
    sys.path.insert(0, project_root)


def nightly_purge() -> int:
    from dotenv import load_dotenv

    load_dotenv(Path(project_root) / ".env")

    from app import create_app
    from app.utils.redis_utils import get_redis_client

    app = create_app()
    with app.app_context():
        redis_client = get_redis_client()
        if redis_client is None:
            print(f"[{datetime.now()}] Warning: Redis client unavailable; skipping zombie purge.")
            return 1

        purged_count = 0
        for raw_key in redis_client.scan_iter("*"):
            key_str = raw_key.decode("utf-8") if isinstance(raw_key, bytes) else str(raw_key)
            if key_str.startswith(("mfa", "rate", "session")) and redis_client.ttl(raw_key) == -1:
                redis_client.delete(raw_key)
                purged_count += 1

        print(f"[{datetime.now()}] Success: Purged {purged_count} zombie keys.")
        return 0


if __name__ == "__main__":
    try:
        sys.exit(nightly_purge())
    except Exception as e:
        print(f"[{datetime.now()}] Error during nightly purge: {e}", file=sys.stderr)
        sys.exit(1)
