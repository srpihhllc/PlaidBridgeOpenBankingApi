# /home/srpihhllc/PlaidBridgeOpenBankingApi/app/utils/schema_drift_detector.py

import json
import logging
import os


_logger = logging.getLogger(__name__)


def detect_schema_drift(redis_client=None) -> dict:
    """Compares current manifest against stable baseline."""
    curr_path = "storage/manifest/model_manifest.json"
    stab_path = "storage/manifest/model_manifest_stable.json"

    report = {
        "drift_detected": False,
        "drift_details": {},
        "models_scanned": 0,
    }

    if not os.path.exists(curr_path) or not os.path.exists(stab_path):
        _logger.warning("Baseline or current manifest missing.")
        return report

    with open(curr_path, "r") as f:
        current_data = json.load(f)
    with open(stab_path, "r") as f:
        stable_data = {m["name"]: m for m in json.load(f)}

    for model in current_data:
        if model.get("status") != "active":
            continue
        report["models_scanned"] += 1
        name = model["name"]

        if (
            name in stable_data
            and model["schema_hash"] != stable_data[name]["schema_hash"]
        ):
            report["drift_detected"] = True
            report["drift_details"][name] = "Schema hash mismatch detected."

    return report
