# app/models/complaint_log.py

from app.extensions import db


class ComplaintLog(db.Model):
    __tablename__ = "complaint_logs"

    id = db.Column(db.Integer, primary_key=True)

    # Transaction.id is String(36) in your repo
    transaction_id = db.Column(
        db.String(36),
        db.ForeignKey("transactions.id", ondelete="CASCADE"),
        nullable=False,
    )

    # ✔ Must match User.id (String(36))
    # ✔ Must include ondelete="CASCADE"
    user_id = db.Column(
        db.String(36),
        db.ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )

    category = db.Column(db.String(64), nullable=True)
    description = db.Column(db.String(64), nullable=True)
    status = db.Column(db.String(32), nullable=True)

    user = db.relationship("User", back_populates="complaint_logs")
    transaction = db.relationship("Transaction", back_populates="complaint_logs")

    def __repr__(self):
        return f"<ComplaintLog {self.id}>"
