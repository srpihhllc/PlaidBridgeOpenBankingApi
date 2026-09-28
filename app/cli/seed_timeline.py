# FILE: app/cli/seed_timeline.py

import os
import random
from datetime import datetime, timedelta, timezone

import click
from flask.cli import with_appcontext

from app.extensions import db
from app.models import TimelineEvent, User


@click.command("seed-timeline")
@with_appcontext
def seed_timeline():
    """Seed timeline analytics for the subscriber dashboard."""

    click.echo("📊 Seeding timeline analytics...")

    target_email = os.environ.get("USER_EMAIL", "subscriber@example.com")
    user = User.query.filter_by(email=target_email).first() or User.query.filter_by(role="subscriber").first()

    if not user:
        raise click.ClickException("❌ Subscriber not found. Seed subscriber first.")

    # Dynamically discover model columns to prevent schema keyword errors
    columns = set(TimelineEvent.__table__.columns.keys())

    for i in range(12):
        kwargs = {}

        if "user_id" in columns:
            kwargs["user_id"] = user.id

        event_name = f"Activity {i+1}"

        if "label" in columns:
            kwargs["label"] = event_name
        if "title" in columns:
            kwargs["title"] = event_name
        if "event_type" in columns:
            kwargs["event_type"] = "user_activity"
        if "description" in columns:
            kwargs["description"] = f"System mock timeline event #{i+1}"
        if "action" in columns:
            kwargs["action"] = "activity_logged"

        if "value" in columns:
            kwargs["value"] = random.randint(10, 100)

        event_ts = datetime.now(timezone.utc) - timedelta(days=i * 3)
        if "timestamp" in columns:
            kwargs["timestamp"] = event_ts
        elif "created_at" in columns:
            kwargs["created_at"] = event_ts

        evt = TimelineEvent(**kwargs)
        db.session.add(evt)

    db.session.commit()
    click.echo("✅ Timeline analytics seeded successfully.")