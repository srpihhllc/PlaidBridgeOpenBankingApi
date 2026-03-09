from app import create_app
from app.extensions import db
import sqlalchemy as sa

app = create_app(env_name="testing")
with app.app_context():
    db.drop_all()
    db.create_all()

    # Use engine.connect() to inspect the raw DDL and PRAGMA on a connection
    with db.engine.connect() as conn:
        ddl = conn.execute(sa.text(
            "SELECT sql FROM sqlite_master WHERE type='table' AND name='bank_transactions'"
        )).fetchone()
        print("=== CREATE TABLE bank_transactions ===")
        print(ddl[0] if ddl else "(no DDL)")

        print("\nPRAGMA foreign_keys before:")
        print(conn.execute(sa.text("PRAGMA foreign_keys")).fetchone())
        conn.execute(sa.text("PRAGMA foreign_keys = ON"))
        print("PRAGMA foreign_keys after:")
        print(conn.execute(sa.text("PRAGMA foreign_keys")).fetchone())

        # Attempt invalid insert on this connection
        try:
            conn.execute(sa.text(
                "INSERT INTO bank_transactions (id, from_account_id, to_account_id, amount) "
                "VALUES (999900, 999999, 999999, 1.0)"
            ))
            print("\nInvalid INSERT completed (no IntegrityError).")
        except Exception as e:
            print("\nInvalid INSERT raised:", type(e).__name__, str(e))
