# =============================================================================
# FILE: app/models/todo.py
# DESCRIPTION: Todo model with UUID user linkage and cascade‑safe semantics.
# =============================================================================

from datetime import date, datetime

from sqlalchemy.orm import DeclarativeBase

from ..extensions import db

# Mypy-safe alias for Flask‑SQLAlchemy dynamic base
Model: type[DeclarativeBase] = db.Model  # type: ignore[attr-defined]


class Todo(Model):
    __tablename__ = "todos"
    __table_args__ = {"extend_existing": True}
    __table_args__ = {"extend_existing": True}

    id = db.Column(db.Integer, primary_key=True)

    # UUID FK with cascade delete
    user_id = db.Column(
        db.String(36),
        db.ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Core fields
    text = db.Column(db.String(255), nullable=False)
    completed = db.Column(db.Boolean, default=False, nullable=False)

    # Upgraded fields
    priority = db.Column(db.String(20), default="normal", nullable=False)  # low|normal|high
    category = db.Column(db.String(50), nullable=True)
    due_date = db.Column(db.Date, nullable=True)
    notes = db.Column(db.Text, nullable=True)

    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(
        db.DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False,
    )

    # Relationship back to User
    user = db.relationship("User", back_populates="todos")

    # Business logic
    def is_overdue(self) -> bool:
        if self.completed or not self.due_date:
            return False
        return self.due_date < date.today()

    def __repr__(self):
        return f"<Todo id={self.id} user_id={self.user_id} text={self.text!r}>"
