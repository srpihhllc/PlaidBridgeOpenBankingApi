# app/utils/boot_meta.py
import os
import socket
import time


def build_meta():
    return {
        "git": os.getenv("GIT_COMMIT", "unknown"),
        "version": os.getenv("APP_VERSION", "0.0.0"),
        "env": os.getenv("FLASK_ENV", "production"),
        "host": socket.gethostname(),
        "started_at": int(time.time()),
    }
