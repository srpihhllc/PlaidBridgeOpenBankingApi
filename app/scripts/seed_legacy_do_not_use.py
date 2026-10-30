# /home/srpihhllc/PlaidBridgeOpenBankingApi/app/scripts/seed.py

"""
Relationship audit script for inspecting SQLAlchemy model relationships,
foreign keys, and navigational attributes.
"""

import logging
from typing import Any
from sqlalchemy.inspection import inspect as sa_inspect

from app.database import Base


logger = logging.getLogger(__name__)


def get_model_name(obj: Any) -> str:
    """Safely extracts and returns the string name of a model or object."""
    name = getattr(obj, "__name__", None)
    if isinstance(name, str):
        return name
    return str(name)


def audit_relationships() -> None:
    """Inspects and prints model relationships across SQLAlchemy metadata."""
    print("🚀 Starting SQLAlchemy Relationship Audit...")

    for mapper in Base.registry.mappers:
        class_ = mapper.class_
        model_name = get_model_name(class_)
        print(f"\nModel: {model_name}")

        inspection = sa_inspect(class_)
        if inspection and hasattr(inspection, "relationships"):
            for rel_name, rel in inspection.relationships.items():
                target_entity = get_model_name(rel.mapper.class_)
                print(f"  - Relationship: {rel_name} -> Target: {target_entity} (Direction: {rel.direction.name})")


if __name__ == "__main__":
    audit_relationships()