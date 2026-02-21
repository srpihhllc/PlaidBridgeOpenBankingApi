# =============================================================================
# FILE: app/signals/schema_listener.py
# DESCRIPTION: Background Redis Pub/Sub listener for schema:update events.
#              Runs in a daemon thread with explicit app context.
#              Safe against Redis outages and context imbalance.
# =============================================================================

import threading

from app.utils.redis_utils import get_redis_client


def schema_listener(app):
    """
    Launch a background thread to listen for schema:update events on Redis Pub/Sub.
    - Each thread manages its own app context.
    - Fails gracefully if Redis is unavailable.
    - Must be called from the application factory: schema_listener(app).
    """

    def _listen():
        # Each background thread manages its own app context
        with app.app_context():
            r = get_redis_client()
            if not r:
                app.logger.error(
                    "[schema_listener] Redis unavailable — cannot subscribe to schema:update"
                )
                return

            try:
                pubsub = r.pubsub(ignore_subscribe_messages=True)
                pubsub.subscribe("schema:update")
                app.logger.info("[schema_listener] Subscribed to schema:update channel.")
            except Exception as e:
                app.logger.error(f"[schema_listener] Failed to subscribe: {e}")
                return

            for message in pubsub.listen():
                if message.get("type") != "message":
                    continue

                raw_data = message.get("data")
                try:
                    revision = (
                        raw_data.decode()
                        if isinstance(raw_data, bytes | bytearray)
                        else str(raw_data)
                    )
                except Exception as e:
                    app.logger.warning(f"[schema_listener] Failed to decode revision: {e}")
                    continue

                app.logger.info(f"[🧠 schema_listener] Detected schema update: {revision}")
                try:
                    from app.signals.triggers import handle_schema_update

                    handle_schema_update(revision)
                except Exception as e:
                    app.logger.error(f"[schema_listener] Error handling schema update: {e}")

    # Start the listener in a daemon thread so it won’t block shutdown
    t = threading.Thread(target=_listen, daemon=True, name="SchemaListenerThread")
    t.start()
    app.logger.debug("[schema_listener] Background thread started.")
