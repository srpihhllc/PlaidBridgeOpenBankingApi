# /home/srpihhllc/PlaidBridgeOpenBankingApi/app/utils/export.py

import csv
import io
import json


def serialize_logs_as_json(logs):
    return json.dumps(logs, indent=2)


def serialize_logs_as_csv(logs):
    output = io.StringIO()
    writer = csv.DictWriter(
        output,
        fieldnames=["event_type", "by", "card_id", "timestamp", "reason", "method"],
    )
    writer.writeheader()
    for log in logs:
        writer.writerow(
            {
                "event_type": log.get("event_type"),
                "by": log.get("by"),
                "card_id": log.get("card_id"),
                "timestamp": log.get("timestamp"),
                "reason": log.get("reason"),
                "method": log.get("method"),
            }
        )
    return output.getvalue()
