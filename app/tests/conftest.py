from app.extensions import db
from sqlalchemy import event

# Ensure SQLite enforces foreign keys on every DBAPI connection created by SQLAlchemy.
# This runs at test-collection time and makes PRAGMA foreign_keys=ON automatic for all connections.
try:
    if db.engine and db.engine.dialect.name == "sqlite":
        event.listen(
            db.engine,
            "connect",
            lambda dbapi_conn, _rec: dbapi_conn.execute("PRAGMA foreign_keys=ON")
        )
except Exception:
    # If engine isn't ready yet in some test setups, fall back to existing per-test safety checks.
    pass
