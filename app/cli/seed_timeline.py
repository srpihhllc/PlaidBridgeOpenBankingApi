# FILE: app/cli/seed_timeline.py

import random
from datetime import datetime, timedelta

import click
from flask.cli import with_appcontext

from app.extensions import db
from app.models import TimelineEvent, User


@click.command("seed-timeline")
@with_appcontext
def seed_timeline():
    """Seed timeline analytics for the subscriber dashboard."""

    click.echo("📊 Seeding timeline analytics...")

    user = User.query.filter_by(email="subscriber@example.com").first()
    if not user:
        click.echo("❌ Subscriber not found.")
        return

    for i in range(12):
        evt = TimelineEvent(
            user_id=user.id,
            label=f"Activity {i+1}",
            value=random.randint(10, 100),
            timestamp=datetime.utcnow() - timedelta(days=i * 3),
        )
        db.session.add(evt)

    db.session.commit()
    click.echo("✅ Timeline analytics seeded.")
