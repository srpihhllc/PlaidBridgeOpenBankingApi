import sys
import sqlalchemy as sa

# ensure repo root is importable
sys.path.insert(0, ".")

# Import factory the same way the application uses it (top-level 'app' package)
from app import create_app

# create app using the environment name the factory expects
app = create_app("testing")

# Import db AFTER the app factory to avoid duplicate-table mapping problems
from app.extensions import db

with app.app_context():
    # create tables as tests do
    db.create_all()

    # Acquire a Connection the same way tests use it
    conn = db.session.connection()

    # 1) show the CREATE TABLE DDL for bank_transactions
    row = conn.execute(sa.text(
        "SELECT sql FROM sqlite_master WHERE type='table' AND name='bank_transactions'"
    )).fetchone()
    ddl = row[0] if row else "<no-ddl>"
    print("==== bank_transactions DDL ====")
    print(ddl)
    print()

    # 2) show PRAGMA foreign_keys for this connection
    fk_on = conn.execute(sa.text("PRAGMA foreign_keys")).fetchone()
    print("PRAGMA foreign_keys =>", fk_on[0] if fk_on else fk_on)
    print()

    # 3) list foreign keys declared on bank_transactions (SQLite pragma)
    fk_list = conn.execute(sa.text("PRAGMA foreign_key_list('bank_transactions')")).fetchall()
    print("PRAGMA foreign_key_list('bank_transactions') rows:", len(fk_list))
    for fk in fk_list:
        print(fk)
    print()

    # 4) simple sanity: list table names
    tables = conn.execute(sa.text("SELECT name FROM sqlite_master WHERE type='table'")).fetchall()
    print("Tables:", [t[0] for t in tables])
