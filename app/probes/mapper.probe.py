# app/probes/mapper_probe.py

# app/probes/mapper_probe.py

from sqlalchemy.orm import class_mapper
from sqlalchemy.orm.exc import UnmappedClassError

from app.extensions import db
from app.telemetry.ttl_emit import trace_log  # ✔ Correct source for trace_log
from app.utils.redis_trace import emit_ttl_trace
from app.utils.telemetry import log_identity_event


def validate_mapper_relationships():
    """
    Validates SQLAlchemy back-populated relationships across all mapped classes.
    Emits cockpit-grade traces, TTL overlays, and identity events.
    """
    errors_found = False
    total_models = 0
    total_relationships = 0
    failed_relationships = []

    try:
        mapped_classes = db.Model.registry._class_registry.values()

        for cls in mapped_classes:
            try:
                mapper = class_mapper(cls)
                total_models += 1

                for prop in mapper.iterate_properties:
                    if hasattr(prop, "back_populates") and prop.back_populates:
                        total_relationships += 1
                        other_mapper = prop.mapper.class_

                        try:
                            getattr(other_mapper, prop.back_populates)

                            trace_log(
                                "mapper/validation/success",
                                (
                                    f"✅ '{cls.__name__}' relationship to "
                                    f"'{other_mapper.__name__}' via '{prop.key}' "
                                    f"and '{prop.back_populates}' is correctly configured."
                                ),
                            )

                            emit_ttl_trace(
                                f"mapper/health/{cls.__name__}/{prop.key}",
                                {
                                    "status": "ok",
                                    "model": cls.__name__,
                                    "related_model": other_mapper.__name__,
                                    "back_populates": prop.back_populates,
                                },
                                ttl=3600,
                            )

                        except AttributeError:
                            errors_found = True
                            failed_relationships.append(
                                {
                                    "model": cls.__name__,
                                    "related_model": other_mapper.__name__,
                                    "missing_property": prop.back_populates,
                                }
                            )

                            trace_log(
                                "mapper/validation/error",
                                (
                                    f"❌ '{other_mapper.__name__}' is missing "
                                    f"back_populates '{prop.back_populates}' for "
                                    f"relationship from '{cls.__name__}' via '{prop.key}'."
                                ),
                            )

                            emit_ttl_trace(
                                f"mapper/health/{cls.__name__}/{prop.key}",
                                {
                                    "status": "error",
                                    "model": cls.__name__,
                                    "related_model": other_mapper.__name__,
                                    "missing_property": prop.back_populates,
                                },
                                ttl=3600,
                            )

                            log_identity_event(
                                user_id=0,
                                event_type="MAPPER_INIT_FAIL",
                                details={
                                    "model": cls.__name__,
                                    "missing_property": prop.back_populates,
                                    "related_model": other_mapper.__name__,
                                    "status": "error",
                                },
                            )

            except UnmappedClassError:
                continue

        # Emit summary trace
        emit_ttl_trace(
            "mapper/health/summary",
            {
                "status": "ok" if not errors_found else "error",
                "total_models": total_models,
                "total_relationships": total_relationships,
                "failed_relationships": failed_relationships,
            },
            ttl=3600,
        )

        if not errors_found:
            trace_log(
                "mapper/validation/complete",
                "All SQLAlchemy relationships validated successfully. Boot complete.",
            )
        else:
            trace_log(
                "mapper/validation/incomplete",
                f"{len(failed_relationships)} relationship errors found during mapper validation.",
            )

    except Exception as e:
        trace_log(
            "mapper/validation/exception",
            f"An unexpected error occurred during mapper validation: {e}",
        )

        emit_ttl_trace(
            "mapper/health/summary",
            {"status": "exception", "error": str(e)},
            ttl=3600,
        )

        log_identity_event(
            user_id=0,
            event_type="MAPPER_INIT_EXCEPTION",
            details={"error_details": str(e), "status": "exception"},
        )
