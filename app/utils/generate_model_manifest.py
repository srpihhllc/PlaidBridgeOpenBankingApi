# app/utils/generate_model_manifest.py

import importlib
import json
from datetime import datetime

from app.models import __all__ as model_names


def generate_manifest():
    manifest = []
    for name in model_names:
        try:
            model = getattr(importlib.import_module("app.models"), name)
            _ = model  # Explicit no-op to silence linter and preserve future introspection
            manifest.append(
                {
                    "name": name,
                    "status": "✅ Imported",
                    "timestamp": datetime.utcnow().isoformat(),
                }
            )
        except Exception as e:
            manifest.append(
                {
                    "name": name,
                    "status": f"⚠️ Failed: {str(e)}",
                    "timestamp": datetime.utcnow().isoformat(),
                }
            )
    with open("storage/manifest/model_manifest.json", "w") as f:
        json.dump(manifest, f, indent=2)


if __name__ == "__main__":
    generate_manifest()
