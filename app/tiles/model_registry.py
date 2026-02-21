# /home/srpihhllc/PlaidBridgeOpenBankingApi/app/tiles/model_registry.py

import json
from datetime import datetime, timedelta

from flask import current_app

from app.utils.redis_utils import get_redis_client  # ✅ centralised, SSL‑safe client


class ModelRegistryTile:
    def __init__(
        self,
        manifest_path="storage/manifest/model_manifest.json",
        stale_threshold_minutes=60,
    ):
        self.manifest_path = manifest_path
        self.redis = get_redis_client()
        self.stale_threshold = timedelta(minutes=stale_threshold_minutes)
        self.models = self.load_manifest()

    def load_manifest(self):
        try:
            with open(self.manifest_path) as f:
                return json.load(f)
        except Exception as e:
            current_app.logger.error(f"[ModelRegistryTile] Failed to load manifest: {e}")
            return []

    def is_stale(self, model_name):
        if not self.redis:
            current_app.logger.error(
                "[ModelRegistryTile] Redis unavailable — marking model as stale by default"
            )
            return True

        key = f"trace:model:{model_name}:last_used"
        try:
            last_used = self.redis.get(key)
        except Exception as e:
            current_app.logger.error(f"[ModelRegistryTile] Failed to get key={key}: {e}")
            return True

        if not last_used:
            return True

        try:
            last_dt = datetime.fromisoformat(last_used.decode())
            return datetime.utcnow() - last_dt > self.stale_threshold
        except Exception as e:
            current_app.logger.warning(
                f"[ModelRegistryTile] Failed to parse timestamp for {model_name}: {e}"
            )
            return True

    def annotate_staleness(self):
        for model in self.models:
            if model.get("status", "").startswith("✅"):
                if self.is_stale(model.get("name")):
                    model["status"] = "💤 Stale"
                else:
                    model["status"] = "🧠 Active"
        return self.models

    def get_status_summary(self):
        summary = {"✅ Imported": 0, "⚠️ Failed": 0, "💤 Stale": 0, "🧠 Active": 0}
        for model in self.models:
            status = model.get("status", "").split(":")[0]
            if status in summary:
                summary[status] += 1
        return summary

    def to_dict(self):
        self.models = self.annotate_staleness()
        return {"summary": self.get_status_summary(), "models": self.models}
