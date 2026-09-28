# FILE: app/cli/seed_todos.py

import os
import random
from datetime import datetime, timedelta, timezone

import click
from flask.cli import with_appcontext

from app.extensions import db
from app.models import Todo, User


@click.command("seed-todos")
@with_appcontext
def seed_todos():
    """Seed sample todo items for the subscriber dashboard."""

    click.echo("📝 Seeding todos...")

    target_email = os.environ.get("USER_EMAIL", "subscriber@example.com")
    user = User.query.filter_by(email=target_email).first() or User.query.filter_by(role="subscriber").first()

    if not user:
        raise click.ClickException("❌ Subscriber not found. Seed subscriber first.")

    # Dynamically discover model columns to prevent schema keyword errors
    columns = set(Todo.__table__.columns.keys())

    sample_tasks = [
        "Connect primary checking account via Plaid",
        "Verify business EIN and address details",
        "Configure multi-factor authentication (MFA)",
        "Review monthly CFPB telemetry report",
        "Generate API integration tokens",
        "Complete subscriber profile onboarding",
    ]

    for i, task_text in enumerate(sample_tasks):
        kwargs = {}

        if "user_id" in columns:
            kwargs["user_id"] = user.id

        # Map task name/content field across possible schema column names
        if "task" in columns:
            kwargs["task"] = task_text
        elif "description" in columns:
            kwargs["description"] = task_text
        elif "text" in columns:
            kwargs["text"] = task_text
        elif "title" in columns:
            kwargs["title"] = task_text
        elif "name" in columns:
            kwargs["name"] = task_text
        elif "content" in columns:
            kwargs["content"] = task_text
        elif "item" in columns:
            kwargs["item"] = task_text

        # Map completion flag
        is_done = (i % 2 == 0)
        if "is_completed" in columns:
            kwargs["is_completed"] = is_done
        elif "completed" in columns:
            kwargs["completed"] = is_done
        elif "done" in columns:
            kwargs["done"] = is_done
        elif "status" in columns:
            kwargs["status"] = "completed" if is_done else "pending"

        # Map timestamps or due dates
        now = datetime.now(timezone.utc)
        if "created_at" in columns:
            kwargs["created_at"] = now - timedelta(days=i)
        if "due_date" in columns:
            kwargs["due_date"] = now + timedelta(days=i + 1)
        if "timestamp" in columns:
            kwargs["timestamp"] = now - timedelta(days=i)

        # Map priority if column exists
        if "priority" in columns:
            kwargs["priority"] = random.choice(["low", "medium", "high"])

        todo_item = Todo(**kwargs)
        db.session.add(todo_item)

    db.session.commit()
    click.echo("✅ Todos seeded successfully.")