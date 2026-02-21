# /home/srpihhllc/PlaidBridgeOpenBankingApi/scripts/cron_purge_zombies.py

import sys
from datetime import datetime

# Add project root to path so we can import our utils
project_root = "/home/srpihhllc/PlaidBridgeOpenBankingApi"
sys.path.append(project_root)


def nightly_purge():
    from app.utils.redis_utils import get_redis_client

    try:
        redis_client = get_redis_client()
        keys = redis_client.keys("*")
        purged_count = 0

        for k in keys:
            if redis_client.ttl(k) == -1:
                key_str = k.decode()
                if key_str.startswith(("mfa", "rate", "session")):
                    redis_client.delete(k)
                    purged_count += 1

        print(f"[{datetime.now()}] Success: Purged {purged_count} zombie keys.")
    except Exception as e:
        print(f"[{datetime.now()}] Error during nightly purge: {e}")


if __name__ == "__main__":
    nightly_purge()
