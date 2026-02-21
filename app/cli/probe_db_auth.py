# app/cli/probe_db_auth.py


def run():
    from app import db
    from app.config import DB_HOST
    from app.trace import trace_event

    try:
        db.session.execute("SELECT 1")
        trace_event("db_auth_success", {"host": DB_HOST})
        print("✅ DB connection successful")
    except Exception as e:
        trace_event("db_auth_failure", {"host": DB_HOST, "error": str(e)})
        print("❌ DB connection failed:", str(e))
