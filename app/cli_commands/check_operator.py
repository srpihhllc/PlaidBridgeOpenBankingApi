import os
import click
from flask.cli import with_appcontext
from flask import current_app
from werkzeug.security import check_password_hash, generate_password_hash
from app.extensions import db
from app.models import User

@click.command("check-operator")
@click.option(
    "--seed",
    is_flag=True,
    help="Auto-seed operator user if missing from database.",
)
@click.option(
    "--password",
    default=None,
    help="Verify password hash against the operator user.",
)
@with_appcontext
def check_operator(seed: bool, password: str | None):
    """Audit Gods Mode config flags, verify operator DB record, and optionally seed or check credentials."""
    click.secho("\n=== 1. GODS MODE CONFIG STATUS ===", fg="cyan", bold=True)
    keys = [
        "OPERATOR_PASSPHRASE",
        "GODS_MODE_PASSPHRASE",
        "TERENCE_PASSPHRASE",
        "OPERATOR_PASSWORD",
        "ADMIN_PASSWORD",
    ]
    for k in keys:
        val = current_app.config.get(k) or os.getenv(k)
        if val:
            click.echo(f"{k:<24}: ✅ SET (Length: {len(val)})")
        else:
            click.echo(f"{k:<24}: ❌ NOT SET")

    click.secho("\n=== 2. OPERATOR USER DATABASE STATUS ===", fg="cyan", bold=True)
    user = (
        db.session.query(User)
        .filter(
            (User.username == "terence")
            | (User.role == "admin")
            | (User.role == "operator")
        )
        .first()
    )

    if not user:
        click.secho("❌ No operator/admin user record found in DB.", fg="red", bold=True)
        if seed:
            click.secho("\n[+] Auto-seeding operator user ('terence')...", fg="yellow")
            op_pass = (
                current_app.config.get("OPERATOR_PASSWORD")
                or os.getenv("OPERATOR_PASSWORD")
                or "ChangeMe123!"
            )
            user = User(
                username="terence",
                email="terence@plaidbridge.internal",
                role="operator",
            )
            if hasattr(user, "set_password"):
                user.set_password(op_pass)
            else:
                user.password_hash = generate_password_hash(op_pass)

            db.session.add(user)
            db.session.commit()
            click.secho("✅ Operator user ('terence') successfully created!", fg="green", bold=True)
        else:
            click.secho("💡 Run with --seed to create the missing record automatically.", fg="cyan")
    else:
        role_val = getattr(user, "role", "N/A")
        click.secho(
            f"✅ Operator Record Found: username=\"{user.username}\", role=\"{role_val}\"",
            fg="green",
            bold=True,
        )

    if user and password:
        click.secho("\n=== 3. CREDENTIAL VERIFICATION ===", fg="cyan", bold=True)
        if hasattr(user, "check_password"):
            is_valid = user.check_password(password)
        else:
            is_valid = check_password_hash(getattr(user, "password_hash", ""), password)

        if is_valid:
            click.secho("✅ Password verification PASSED.", fg="green", bold=True)
        else:
            click.secho("❌ Password verification FAILED.", fg="red", bold=True)