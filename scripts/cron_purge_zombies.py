import os
import sys
from datetime import datetime

sys.path.append("/home/srpihhllc/PlaidBridgeOpenBankingApi")

os.environ["FLASK_APP"] = "run.py"

from app.utils.redis_utils import get_redis_client


def nightly_purge():
    try:
        r = get_redis_client()

        keys = r.keys("*")

        purged = 0

        for k in keys:
            if r.ttl(k) == -1:
                # Handle both bytes and strings safely

                ks = k.decode() if hasattr(k, "decode") else k

                if ks.startswith(("mfa", "rate", "session")):
                    r.delete(k)

                    purged += 1

        print(f"[{datetime.now()}] Success: Purged {purged} zombies.")

    except Exception as e:
        print(f"[{datetime.now()}] Error: {e}")


if __name__ == "__main__":
    nightly_purge()
