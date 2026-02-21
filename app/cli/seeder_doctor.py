# FILE: app/cli/seeder_doctor.py

import uuid

import click
from flask.cli import with_appcontext

from app.extensions import db
from app.models import BankAccount, BankInstitution, SubscriberProfile, User, UserDashboard


@click.command("seeder-doctor")
@with_appcontext
def seeder_doctor():
    """
    Cockpit‑grade Seeder Doctor.
    Audits and auto‑repairs subscriber ecosystem integrity.
    """

    click.echo("\n🔍 Running Seeder Doctor...\n")

    report = {
        "fixed_uuid": 0,
        "fixed_missing_dashboards": 0,
        "fixed_missing_profiles": 0,
        "fixed_orphan_institutions": 0,
        "fixed_orphan_accounts": 0,
        "fixed_missing_api_keys": 0,
        "fixed_mismatched_roles": 0,
    }

    # -------------------------------------------------------------------------
    # 1. UUID Integrity Check
    # -------------------------------------------------------------------------
    users = User.query.all()
    for u in users:
        if not u.uuid or u.uuid.strip() == "":
            u.uuid = str(uuid.uuid4())
            report["fixed_uuid"] += 1

    # -------------------------------------------------------------------------
    # 2. Missing Dashboards
    # -------------------------------------------------------------------------
    for u in users:
        if not u.user_dashboard:
            dashboard = UserDashboard(user_id=u.id)
            db.session.add(dashboard)
            report["fixed_missing_dashboards"] += 1

    # -------------------------------------------------------------------------
    # 3. Missing Subscriber Profiles
    # -------------------------------------------------------------------------
    for u in users:
        if u.role == "subscriber" and not u.subscriber_profile:
            profile = SubscriberProfile(user_id=u.id)
            profile.generate_api_key()
            db.session.add(profile)
            report["fixed_missing_profiles"] += 1

    # -------------------------------------------------------------------------
    # 4. Orphaned Bank Institutions
    # -------------------------------------------------------------------------
    institutions = BankInstitution.query.all()
    for inst in institutions:
        if not User.query.get(inst.user_id):
            db.session.delete(inst)
            report["fixed_orphan_institutions"] += 1

    # -------------------------------------------------------------------------
    # 5. Orphaned Bank Accounts
    # -------------------------------------------------------------------------
    accounts = BankAccount.query.all()
    for acct in accounts:
        if not User.query.get(acct.user_id):
            db.session.delete(acct)
            report["fixed_orphan_accounts"] += 1

    # -------------------------------------------------------------------------
    # 6. Missing API Keys
    # -------------------------------------------------------------------------
    profiles = SubscriberProfile.query.all()
    for p in profiles:
        if not p.api_key:
            p.generate_api_key()
            report["fixed_missing_api_keys"] += 1

    # -------------------------------------------------------------------------
    # 7. Mismatched Roles
    # -------------------------------------------------------------------------
    for u in users:
        if u.is_admin and u.role != "admin":
            u.role = "admin"
            report["fixed_mismatched_roles"] += 1
        if not u.is_admin and u.role != "subscriber":
            u.role = "subscriber"
            report["fixed_mismatched_roles"] += 1

    # -------------------------------------------------------------------------
    # Commit all repairs
    # -------------------------------------------------------------------------
    db.session.commit()

    # -------------------------------------------------------------------------
    # Cockpit‑grade Report
    # -------------------------------------------------------------------------
    click.echo("🩺 Seeder Doctor Report")
    click.echo("----------------------------------------")
    click.echo(f"🔧 UUIDs repaired:                 {report['fixed_uuid']}")
    click.echo(f"🔧 Missing dashboards fixed:       {report['fixed_missing_dashboards']}")
    click.echo(f"🔧 Missing profiles fixed:         {report['fixed_missing_profiles']}")
    click.echo(f"🔧 Orphan institutions removed:    {report['fixed_orphan_institutions']}")
    click.echo(f"🔧 Orphan accounts removed:        {report['fixed_orphan_accounts']}")
    click.echo(f"🔧 Missing API keys generated:     {report['fixed_missing_api_keys']}")
    click.echo(f"🔧 Mismatched roles corrected:     {report['fixed_mismatched_roles']}")
    click.echo("----------------------------------------")
    click.echo("✅ Seeder Doctor completed.\n")
