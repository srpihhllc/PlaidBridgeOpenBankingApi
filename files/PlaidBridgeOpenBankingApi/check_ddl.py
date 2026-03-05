import sys
import sqlalchemy as sa

# ensure repo root is importable
sys.path.insert(0, ".")

# import your app factory + db
from PlaidBridgeOpenBankingApi.app import create_app
from PlaidBridgeOpenBankingApi.app.extensions import db

# create the app, then set TESTING via config update so we don't pass a dict to create_app
app = create_app()
app.config.update({"TESTING": True})

with app.app_context():
    # create tables as tests do
    db.create_all()

    # Use the same connection style the tests use
    conn = db.session.connection()

    # 1) show the CREATE TABLE DDL
    row = conn.execute(sa.text("SELECT sql FROM sqlite_master WHERE type='table' AND name='bank_transactions'")).fetchone()
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
