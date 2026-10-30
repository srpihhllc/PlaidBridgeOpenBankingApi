# =============================================================================
# FILE: app/models/user_dashboard.py
# DESCRIPTION: Subscriber dashboard settings model with UUID FK linkage,
#              cockpit-grade defaults, and safe update helpers.
# =============================================================================

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, cast

from ..extensions import db

Model: Any = db.Model


class UserDashboard(Model):
    __tablename__ = "user_dashboards"
    __table_args__ = {"extend_existing": True}

    id = db.Column(db.Integer, primary_key=True)

    user_id = db.Column(
        db.String(36),
        db.ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )

    settings = db.Column(db.JSON, nullable=True)

    created_at = db.Column(
        db.DateTime,
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    updated_at = db.Column(
        db.DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    user = db.relationship(
        "User",
        backref=db.backref(
            "user_dashboard",
            uselist=False,
            passive_deletes=True,
        ),
    )

    @staticmethod
    def default_settings() -> dict[str, Any]:
        return {
            "layout": "two_column",
            "theme": "light",
            "show_todo_tile": True,
            "show_today_widget": True,
            "show_balance_tile": True,
            "show_activity_tile": True,
            "todo_sort": "created",
            "todo_filter": "all",
            "default_priority": "normal",
            "default_category": None,
        }

    @classmethod
    def create_for_user(cls, user_id: str) -> UserDashboard:
        return cls(
            user_id=user_id,
            settings=cls.default_settings(),
        )

    def get_setting(self, key: str, default: Any = None) -> Any:
        settings = self.settings
        if not isinstance(settings, dict):
            return default
        return settings.get(key, default)

    def set_setting(self, key: str, value: Any) -> dict[str, Any]:
        settings = self.settings
        if not isinstance(settings, dict):
            settings = {}
            self.settings = settings

        typed_settings = cast(dict[str, Any], settings)
        typed_settings[key] = value
        return typed_settings

    def enable_widget(self, widget_name: str) -> dict[str, Any]:
        return self.set_setting(widget_name, True)

    def disable_widget(self, widget_name: str) -> dict[str, Any]:
        return self.set_setting(widget_name, False)

    def toggle_widget(self, widget_name: str) -> dict[str, Any]:
        current = self.get_setting(widget_name, False)
        return self.set_setting(widget_name, not current)

    def save(self) -> UserDashboard:
        db.session.add(self)
        db.session.commit()
        return self

    def __repr__(self) -> str:
        return (
            f"<UserDashboard user_id={self.user_id} "
            f"layout={self.get_setting('layout')}>"
        )