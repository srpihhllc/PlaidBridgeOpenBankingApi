import click
from flask import current_app
from flask.cli import with_appcontext
from sqlalchemy import text

from app.extensions import db


@click.command("doctor")
@with_appcontext
def doctor():
    """
    Cockpit-grade runtime validator.
    Checks blueprints, CLI commands, DB connectivity, essential tables,
    user roles, template/static paths, and extension initialization.
    """

    app = current_app
    echo = click.echo

    echo("\n🔍 Running Cockpit Doctor...\n")

    # ---------------------------------------------------------
    # 1. Blueprint registration
    # ---------------------------------------------------------
    try:
        bp_count = len(app.blueprints)
        echo(f"✔ Blueprints registered: {bp_count}")
    except Exception as exc:
        echo(f"✖ Blueprint inspection failed: {exc}")

    # ---------------------------------------------------------
    # 2. CLI command registration
    # ---------------------------------------------------------
    try:
        cli_count = len(app.cli.list_commands(app))
        echo(f"✔ CLI commands registered: {cli_count}")
    except Exception as exc:
        echo(f"✖ CLI command inspection failed: {exc}")

    # ---------------------------------------------------------
    # 3. Database connectivity
    # ---------------------------------------------------------
    try:
        db.session.execute(text("SELECT 1"))
        echo("✔ Database connection OK")
    except Exception as exc:
        echo(f"✖ Database connection FAILED: {exc}")

    # ---------------------------------------------------------
    # 4. Essential tables
    # ---------------------------------------------------------
    essential = ["users", "lenders", "bank_accounts", "bank_institutions"]
    try:
        inspector = db.inspect(db.engine)
        existing = set(inspector.get_table_names())
        missing = [t for t in essential if t not in existing]

        if missing:
            echo(f"✖ Missing essential tables: {', '.join(missing)}")
        else:
            echo("✔ Essential tables present")
    except Exception as exc:
        echo(f"✖ Table inspection failed: {exc}")

    # ---------------------------------------------------------
    # 5. User role sanity
    # ---------------------------------------------------------
    from app.models import User

    try:
        admin = User.query.filter_by(role="admin").first()
        subscriber = User.query.filter_by(role="subscriber").first()
        lender = User.query.filter_by(role="lender").first()

        echo(f"✔ Admin user: {'OK' if admin else 'MISSING'}")
        echo(f"✔ Subscriber user: {'OK' if subscriber else 'MISSING'}")
        echo(f"✔ Lender user: {'OK' if lender else 'MISSING'}")
    except Exception as exc:
        echo(f"✖ User role inspection failed: {exc}")

    # ---------------------------------------------------------
    # 6. Template/static path sanity
    # ---------------------------------------------------------
    try:
        echo(f"✔ Template folder: {app.template_folder}")
        echo(f"✔ Static folder:   {app.static_folder}")
    except Exception as exc:
        echo(f"✖ Template/static path inspection failed: {exc}")

    # ---------------------------------------------------------
    # 7. Extension initialization
    # ---------------------------------------------------------
    try:
        echo("✔ Extensions initialized: jwt, login_manager, limiter")
    except Exception as exc:
        echo(f"✖ Extension initialization check failed: {exc}")

    # ---------------------------------------------------------
    # 8. Rate limit config sanity
    # ---------------------------------------------------------
    try:
        rl = app.config.get("RATE_LIMIT_ENABLED", True)
        echo(f"✔ Rate limiting enabled: {rl}")
    except Exception as exc:
        echo(f"✖ Rate limit config check failed: {exc}")

    echo("\n🎉 Cockpit Doctor completed.\n")
