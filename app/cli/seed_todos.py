# FILE: app/cli/seed_todos.py

import random
from datetime import datetime, timedelta

import click
from flask.cli import with_appcontext

from app.extensions import db
from app.models import Todo, User


@click.command("seed-todos")
@with_appcontext
def seed_todos():
    """Seed mock todos for the subscriber."""

    click.echo("📝 Seeding todos...")

    user = User.query.filter_by(email="subscriber@example.com").first()
    if not user:
        click.echo("❌ Subscriber not found.")
        return

    titles = [
        "Review bank statement",
        "Upload documents",
        "Check fraud alerts",
        "Update profile",
        "Verify email",
        "Complete onboarding",
    ]

    for title in titles:
        todo = Todo(
            user_id=user.id,
            title=title,
            priority="normal",
            due_date=datetime.utcnow() + timedelta(days=random.randint(1, 10)),
            is_completed=random.choice([True, False]),
        )
        db.session.add(todo)

    db.session.commit()
    click.echo("✅ Todos seeded.")
