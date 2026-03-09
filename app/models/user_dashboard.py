# =============================================================================
# FILE: app/models/user_dashboard.py
# DESCRIPTION: Subscriber dashboard settings model with UUID FK linkage,
#              cockpit‑grade defaults, and safe update helpers.
# =============================================================================

from datetime import datetime

from ..extensions import db


class UserDashboard(db.Model):
    __tablename__ = "user_dashboards"
    __table_args__ = {"extend_existing": True}
    __table_args__ = {"extend_existing": True}

    id = db.Column(db.Integer, primary_key=True)

    # UUID FK with cascade delete
    user_id = db.Column(
        db.String(36),
        db.ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )

    # JSON settings for layout, widget visibility, preferences
    settings = db.Column(db.JSON, nullable=True)

    # Timestamping for cockpit audits
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(
        db.DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False,
    )

    # Relationship back to User
    user = db.relationship("User", back_populates="user_dashboard")

    # -------------------------------------------------------------------------
    # Default dashboard settings (cockpit‑grade)
    # -------------------------------------------------------------------------
    @staticmethod
    def default_settings():
        return {
            "layout": "two_column",
            "theme": "light",
            # Widget visibility
            "show_todo_tile": True,
            "show_today_widget": True,
            "show_balance_tile": True,
            "show_activity_tile": True,
            # Todo preferences
            "todo_sort": "created",  # created | priority | due
            "todo_filter": "all",  # all | pending | completed
            "default_priority": "normal",
            "default_category": None,
        }

    # -------------------------------------------------------------------------
    # Initialization helper
    # -------------------------------------------------------------------------
    @classmethod
    def create_for_user(cls, user_id: str):
        return cls(
            user_id=user_id,
            settings=cls.default_settings(),
        )

    # -------------------------------------------------------------------------
    # Settings helpers (safe getters/setters)
    # -------------------------------------------------------------------------
    def get_setting(self, key, default=None):
        if not self.settings:
            return default
        return self.settings.get(key, default)

    def set_setting(self, key, value):
        if not self.settings:
            self.settings = {}
        self.settings[key] = value
        return self.settings

    def enable_widget(self, widget_name: str):
        return self.set_setting(widget_name, True)

    def disable_widget(self, widget_name: str):
        return self.set_setting(widget_name, False)

    def toggle_widget(self, widget_name: str):
        current = self.get_setting(widget_name, False)
        return self.set_setting(widget_name, not current)

    # -------------------------------------------------------------------------
    # Commit helper (atomic dashboard updates)
    # -------------------------------------------------------------------------
    def save(self):
        db.session.add(self)
        db.session.commit()
        return self

    # -------------------------------------------------------------------------
    # Representation
    # -------------------------------------------------------------------------
    def __repr__(self):
        return f"<UserDashboard user_id={self.user_id} " f"layout={self.get_setting('layout')}>"
