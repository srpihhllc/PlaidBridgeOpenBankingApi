from app.extensions import db


class IdempotencyKey(db.Model):

    __tablename__ = "idempotency_keys"

    id = db.Column(
        db.BigInteger,
        primary_key=True,
    )

    idempotency_key = db.Column(
        db.String(128),
        unique=True,
        nullable=False,
    )

    response_hash = db.Column(
        db.String(256),
        nullable=False,
    )

    created_at = db.Column(
        db.DateTime,
        nullable=False,
        server_default=db.func.now(),
    )