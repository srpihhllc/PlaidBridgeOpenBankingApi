# /home/srpihhllc/PlaidBridgeOpenBankingApi/app/cli/doctor_pa.py

import click
from flask import current_app
from flask.cli import with_appcontext
from sqlalchemy import text

from app.extensions import db
from app.models.user import User


@click.command("doctor-pa")
@with_appcontext  # Binds Flask app context during execution
def doctor_pa():
    """PythonAnywhere‑compatible Cockpit Doctor."""

    print("\n🔍 Running PythonAnywhere‑Safe Cockpit Doctor...\n")

    # ---------------------------------------------------------
    # 1. CONFIG CHECK
    # ---------------------------------------------------------
    cfg = current_app.config
    print(f"✔ Config class: {cfg.get('ENV', 'unknown')}")

    # ---------------------------------------------------------
    # 2. DB CONNECTION CHECK (SAFE)
    # ---------------------------------------------------------
    try:
        result = db.session.execute(text("SELECT 1")).fetchall()
        print(f"✔ Database connection OK: {result}")
    except Exception as e:
        print(f"✖ Database connection FAILED: {e}")
        db.session.rollback()

    # ---------------------------------------------------------
    # 3. TABLE PRESENCE CHECK (SAFE)
    # ---------------------------------------------------------
    required_tables = [
        "users",
        "subscriber_profile",
        "lenders",
        "access_tokens",
        "audit_logs",
        "todos",
        "trace_events",
    ]

    print("\n📁 Table presence check:")
    for table in required_tables:
        try:
            db.session.execute(text(f"SELECT 1 FROM {table} LIMIT 1"))
            print(f"✔ {table}: OK")
        except Exception:
            print(f"✖ {table}: MISSING or unreadable")
            db.session.rollback()  # Roll back failed transaction state for next query

    # ---------------------------------------------------------
    # 4. USER CHECKS (SAFE)
    # ---------------------------------------------------------
    print("\n👤 User checks:")
    try:
        admin = User.query.filter_by(role="admin").first()
        print("✔ Admin user:", admin.id if admin else "MISSING")
    except Exception:
        print("✖ Admin user lookup failed")
        db.session.rollback()

    try:
        sub = User.query.filter_by(role="subscriber").first()
        print("✔ Subscriber user:", sub.id if sub else "MISSING")
    except Exception:
        print("✖ Subscriber user lookup failed")
        db.session.rollback()

    try:
        lender = User.query.filter_by(role="lender").first()
        print("✔ Lender user:", lender.id if lender else "MISSING")
    except Exception:
        print("✖ Lender user lookup failed")
        db.session.rollback()

    # ---------------------------------------------------------
    # 5. BLUEPRINT CHECK (SAFE)
    # ---------------------------------------------------------
    print("\n📦 Blueprint count:", len(current_app.blueprints))
    print("✔ Blueprints registered:", list(current_app.blueprints.keys()))

    print("\n🎉 PythonAnywhere‑Safe Cockpit Doctor completed.\n")
