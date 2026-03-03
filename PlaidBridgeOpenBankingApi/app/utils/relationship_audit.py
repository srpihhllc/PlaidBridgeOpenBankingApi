# app/utils/relationship_audit.py

from sqlalchemy.orm import configure_mappers


def audit_back_populates():
    """
    Verifies that for every relationship with back_populates,
    the target class actually has the expected attribute.
    """
    try:
        configure_mappers()  # finalize all mappings
    except Exception as e:
        print(f"[MAPPER CONFIG ERROR] {e}")
        raise

    from app import models

    for model_name in getattr(models, "__all__", []):
        model_cls = getattr(models, model_name, None)
        if not model_cls or not hasattr(model_cls, "__mapper__"):
            continue
        for rel in model_cls.__mapper__.relationships:
            target_attr = rel.back_populates
            if target_attr:
                target_cls = rel.mapper.class_
                if not hasattr(target_cls, target_attr):
                    print(
                        f"[MAPPER AUDIT] {model_cls.__name__}.{rel.key} "
                        f"back_populates='{target_attr}' "
                        f"but {target_cls.__name__} has no such attribute."
                    )

def run():
    """
    Compatibility wrapper so scripts/audit.py can call relationship_audit.run().
    Runs audit_back_populates() inside an active Flask app context if one exists,
    otherwise creates a temporary app to run the audit.
    """
    try:
        # Try running inside current app context
        audit_back_populates()
    except RuntimeError:
        # No current_app — create one and run inside its app_context
        from app import create_app

        app = create_app()
        with app.app_context():
            audit_back_populates()
    except Exception as e:
        # Surface other errors but don't crash the orchestrator
        print(f"[ERROR] relationship_audit.audit_back_populates raised: {e}")
