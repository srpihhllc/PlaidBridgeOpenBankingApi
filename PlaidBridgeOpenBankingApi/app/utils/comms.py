def notify_authorities(report):
    from flask import current_app

    current_app.logger.info(f"📣 Notifying regulators: {report}")

    # Optionally emit a trace:
    from app.extensions import db
    from app.models.schema_event import SchemaEvent

    db.session.add(
        SchemaEvent(event_type="REGULATOR_ALERT_ISSUED", origin="comms", detail=str(report))
    )
    db.session.commit()
