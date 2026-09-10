# app/utils/generate_model_manifest.py

import hashlib
import importlib
import json
import os
from datetime import datetime, timezone

from sqlalchemy import inspect

from app.models import __all__ as model_names


def generate_manifest(output_path="storage/manifest/model_manifest.json"):
    """Generates a full introspective manifest of all SQLAlchemy models."""
    manifest = []

    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    models_module = importlib.import_module("app.models")

    for name in model_names:
        try:
            model = getattr(models_module, name)
            inspector = inspect(model)

            columns = [c.name for c in inspector.columns]
            relationships = {
                rel.key: {
                    "target": rel.mapper.class_.__name__,
                    "direction": str(rel.direction),
                    "uselist": rel.uselist,
                }
                for rel in inspector.relationships
            }

            schema_hash = hashlib.sha256(
                json.dumps(
                    {
                        "columns": sorted(columns),
                        "relationships": sorted(relationships.keys()),
                    }
                ).encode()
            ).hexdigest()

            manifest.append(
                {
                    "name": name,
                    "table_name": (
                        inspector.tables[0].name if inspector.tables else "N/A"
                    ),
                    "columns": columns,
                    "column_count": len(columns),
                    "relationships": relationships,
                    "schema_hash": schema_hash,
                    "status": "active",
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                }
            )

        except Exception as e:
            manifest.append(
                {
                    "name": name,
                    "status": f"error: {str(e)}",
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                }
            )

    with open(output_path, "w") as f:
        json.dump(manifest, f, indent=2)

    return manifest
