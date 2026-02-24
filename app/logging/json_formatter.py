# /home/srpihhllc/PlaidBridgeOpenBankingApi/app/logging/json_formatter.py

import json
import logging
import re

SECRET_KEYS = re.compile(r"(password|secret|token|key)", re.I)


class JsonFormatter(logging.Formatter):
    def format(self, record):
        base = {
            "ts": self.formatTime(record, datefmt="%Y-%m-%dT%H:%M:%S%z"),
            "lvl": record.levelname,
            "msg": record.getMessage(),
            "logger": record.name,
        }
        # Optional: attach request_id if present
        try:
            from flask import g

            if getattr(g, "request_id", None):
                base["request_id"] = g.request_id
        except RuntimeError:
            pass
        return json.dumps(base, ensure_ascii=False)
