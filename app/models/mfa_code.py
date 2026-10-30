# =============================================================================
# FILE: app/models/mfa_code.py
# DESCRIPTION: MFA code model with creation, validation, consumption, expiry,
#              failure-count, and cleanup helpers.
# =============================================================================

from __future__ import annotations

import hmac
import logging
from datetime import datetime, timedelta, timezone
from typing import Any, cast

from sqlalchemy.exc import SQLAlchemyError

from ..extensions import db

logger = logging.getLogger(__name__)


def _get_naive_utc_now() -> datetime:
    """Return a naive datetime representing the current UTC time."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


class MFACode(db.Model):
    """A one-time MFA code associated with a user."""

    __tablename__ = "mfa_codes"

    id = db.Column(db.Integer, primary_key=True)

    user_id = db.Column(
        db.String(36),
        db.ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    code = db.Column(db.String(32), nullable=False, index=True)
    created_at = db.Column(
        db.DateTime,
        default=_get_naive_utc_now,
        nullable=False,
    )
    expires_at = db.Column(db.DateTime, nullable=False, index=True)
    fail_count = db.Column(db.Integer, default=0, nullable=False)

    user = db.relationship(
        "User",
        backref=db.backref("mfa_codes", lazy="dynamic"),
        lazy="joined",
    )

    @classmethod
    def create_or_replace(
        cls,
        user_id: str,
        code: str,
        ttl_seconds: int = 600,
        commit: bool = True,
    ) -> MFACode:
        """Replace a user's existing code and create a new one."""
        try:
            existing = cls.query.filter_by(user_id=user_id).first()
            if existing:
                db.session.delete(existing)
                db.session.flush()

            now = _get_naive_utc_now()
            obj = cls(
                user_id=user_id,
                code=code,
                created_at=now,
                expires_at=now + timedelta(seconds=ttl_seconds),
                fail_count=0,
            )
            db.session.add(obj)

            if commit:
                db.session.commit()
            else:
                db.session.flush()

            return obj

        except SQLAlchemyError:
            db.session.rollback()
            logger.exception(
                "Failed to create_or_replace MFACode for user_id=%s",
                user_id,
            )
            raise

    @classmethod
    def get_active_for_user(cls, user_id: str) -> MFACode | None:
        """Return the newest unexpired code for a user, if one exists."""
        now = _get_naive_utc_now()
        result = (
            cls.query.filter_by(user_id=user_id)
            .filter(cls.expires_at > now)
            .order_by(cls.created_at.desc())
            .first()
        )
        return cast(MFACode | None, result)

    def is_valid(self) -> bool:
        """Return whether the code has not expired."""
        expires = self.expires_at
        if expires is None:
            return False

        if expires.tzinfo is None:
            expires = expires.replace(tzinfo=timezone.utc)

        return bool(datetime.now(timezone.utc) < expires)

    def time_remaining(self) -> int:
        """Return seconds remaining until expiry, or zero if expired."""
        expires = self.expires_at
        if expires is None:
            return 0

        if expires.tzinfo is None:
            expires = expires.replace(tzinfo=timezone.utc)

        remaining = int(
            (expires - datetime.now(timezone.utc)).total_seconds()
        )
        return max(0, remaining)

    def increment_fail(self, commit: bool = True) -> None:
        """Increment the failure count and optionally commit the change."""
        try:
            self.fail_count = (self.fail_count or 0) + 1
            db.session.add(self)

            if commit:
                db.session.commit()
            else:
                db.session.flush()

        except SQLAlchemyError:
            db.session.rollback()
            logger.exception(
                "Failed to increment fail_count for MFACode id=%s",
                getattr(self, "id", None),
            )
            raise

    def consume(self, commit: bool = True) -> None:
        """Delete this code so it can no longer be used."""
        try:
            db.session.delete(self)

            if commit:
                db.session.commit()
            else:
                db.session.flush()

        except SQLAlchemyError:
            db.session.rollback()
            logger.exception(
                "Failed to consume MFACode id=%s",
                getattr(self, "id", None),
            )
            raise

    def validate_and_consume(
        self,
        submitted_code: str,
        max_failures: int = 10,
    ) -> bool:
        """Validate the submitted code, consume it on success, and track failures."""
        if not self.is_valid():
            try:
                db.session.delete(self)
                db.session.commit()
            except SQLAlchemyError:
                db.session.rollback()
                logger.exception(
                    "Failed to delete expired MFACode id=%s",
                    getattr(self, "id", None),
                )
            return False

        if secrets_compare(submitted_code, self.code):
            self.consume(commit=True)
            return True

        try:
            self.increment_fail(commit=False)

            if (self.fail_count or 0) >= max_failures:
                db.session.delete(self)

            db.session.commit()
        except SQLAlchemyError:
            db.session.rollback()
            logger.exception(
                "Failed to handle verification failure or lockout purge "
                "for MFACode id=%s",
                getattr(self, "id", None),
            )

        return False

    @classmethod
    def purge_expired(cls, older_than_seconds: int | None = None) -> int:
        """Delete expired codes, optionally waiting past their expiry."""
        now = _get_naive_utc_now()
        threshold = (
            now
            if older_than_seconds is None
            else now - timedelta(seconds=older_than_seconds)
        )

        try:
            statement = cls.__table__.delete().where(
                cls.expires_at <= threshold
            )
            result = db.session.execute(statement)
            db.session.commit()
            return int(result.rowcount or 0)

        except SQLAlchemyError:
            db.session.rollback()
            logger.exception("Failed to purge expired MFACode rows")
            raise

    @classmethod
    def list_for_user(cls, user_id: str) -> list[dict[str, Any]]:
        """Return serializable summaries of a user's MFA code rows."""
        rows = (
            cls.query.filter_by(user_id=user_id)
            .order_by(cls.created_at.desc())
            .all()
        )
        return [
            {
                "id": row.id,
                "code": row.code,
                "created_at": (
                    row.created_at.isoformat() if row.created_at else None
                ),
                "expires_at": (
                    row.expires_at.isoformat() if row.expires_at else None
                ),
                "time_remaining": row.time_remaining(),
                "fail_count": row.fail_count,
            }
            for row in rows
        ]

    def to_dict(self) -> dict[str, Any]:
        """Return a serializable summary without exposing the MFA code."""
        return {
            "id": self.id,
            "user_id": self.user_id,
            "created_at": (
                self.created_at.isoformat() if self.created_at else None
            ),
            "expires_at": (
                self.expires_at.isoformat() if self.expires_at else None
            ),
            "time_remaining": self.time_remaining(),
            "fail_count": self.fail_count,
        }

    def __repr__(self) -> str:
        expires_iso = self.expires_at.isoformat() if self.expires_at else None
        return (
            f"<MFACode id={self.id} user_id={self.user_id} "
            f"expires_at={expires_iso}>"
        )


def secrets_compare(a: str | None, b: str | None) -> bool:
    """Compare two non-empty strings in constant time."""
    if not a or not b:
        return False
    return bool(hmac.compare_digest(str(a), str(b)))