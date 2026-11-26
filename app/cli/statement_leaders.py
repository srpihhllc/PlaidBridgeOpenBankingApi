# app/cli/statement_leaders.py

import click
from sqlalchemy import func

from app.extensions import db
from app.models.bank_statement import BankStatement
from app.models.user import User
from app.telemetry.ttl_emit import trace_log


@click.command("cockpit:statement-leaders")
@click.option("--limit", default=10, show_default=True, help="Max leaders to display.")
def statement_leaders(limit):
    """List cockpit statement leaders."""
    rows = (
        db.session.query(
            User.id,
            User.email,
            func.count(BankStatement.id).label("stmt_count"),
            func.coalesce(func.sum(BankStatement.txn_count), 0).label("total_txns"),
        )
        .join(BankStatement, BankStatement.user_id == User.id)
        .group_by(User.id, User.email)
        .order_by(func.count(BankStatement.id).desc(), func.sum(BankStatement.txn_count).desc())
        .limit(limit)
        .all()
    )
    trace_log("cli/statement_leaders/status", f"Listed {len(rows)} statement leaders")
    if not rows:
        click.echo("📊 No statement leaders found.")
        return
    for rank, (uid, email, count, txns) in enumerate(rows, start=1):
        click.echo(f"📊 {rank}. user_id={uid} ({email}) - {count} statements ({txns} txns)")
