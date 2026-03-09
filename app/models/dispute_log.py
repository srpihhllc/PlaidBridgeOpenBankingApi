# app/models/dispute_log.py

import hashlib
import os
from datetime import datetime

from ..extensions import db


class DisputeLog(db.Model):
    __tablename__ = "dispute_log"
    __table_args__ = {"extend_existing": True}
    __table_args__ = {"extend_existing": True}

    id = db.Column(db.Integer, primary_key=True)

    # ✔ Must match User.id (String(36))
    # ✔ Must include ondelete="CASCADE"
    user_id = db.Column(
        db.String(36),
        db.ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )

    template_title = db.Column(db.String(128), nullable=False)
    bureau = db.Column(db.String(64), nullable=False)
    method = db.Column(db.String(16), nullable=False)
    email_status = db.Column(db.String(16), default="n/a")
    sendgrid_id = db.Column(db.String(128), nullable=True)

    content_hash = db.Column(db.String(128), nullable=False)
    delivery_ts = db.Column(db.DateTime, default=datetime.utcnow)
    acknowledged_ts = db.Column(db.DateTime, nullable=True)
    response_notes = db.Column(db.Text, nullable=True)

    status = db.Column(db.String(32), default="sent")

    # ✔ Correct parent relationship
    user = db.relationship("User", back_populates="dispute_logs")

    # ---------- Artifact Trace Properties ----------
    @property
    def txt_path(self):
        return f"storage/disputes/{self.id}.txt"

    @property
    def pdf_path(self):
        return f"storage/disputes/{self.id}.pdf"

    @property
    def zip_path(self):
        return f"storage/bundles/dispute_{self.id}_bundle.zip"

    @property
    def txt_exists(self):
        return os.path.exists(self.txt_path)

    @property
    def pdf_exists(self):
        return os.path.exists(self.pdf_path)

    @property
    def zip_exists(self):
        return os.path.exists(self.zip_path)

    # ---------- Download Routes ----------
    @property
    def download_txt_url(self):
        return f"/api/download/letter/{self.id}"

    @property
    def download_pdf_url(self):
        return f"/api/download/pdf/{self.id}"

    @property
    def download_zip_url(self):
        return f"/api/download/bundle/{self.id}"

    # ---------- Content Hash Verification ----------
    def verify_content_hash(self):
        if not self.txt_exists:
            return False
        with open(self.txt_path, "rb") as f:
            actual = hashlib.sha256(f.read()).hexdigest()
        return actual == self.content_hash

    # ---------- Dispatch State Summary ----------
    @property
    def dispatch_state(self):
        if self.status == "acknowledged":
            return "✅ Acknowledged"
        if self.status == "sent" and not self.pdf_exists:
            return "📄 Sent (no PDF)"
        if self.status == "sent" and self.pdf_exists:
            return "🧾 Sent w/ Artifact"
        return "❌ Unknown"

    # ---------- Badge Generator ----------
    def get_badges(self):
        badges = []
        if self.pdf_exists:
            badges.append("🟢 PDF attached")
        if self.zip_exists:
            badges.append("🟣 ZIP available")
        if self.verify_content_hash():
            badges.append("🧠 Hash verified")
        return badges

    # ---------- JSON Export ----------
    def to_dict(self):
        return {
            "id": self.id,
            "user_id": self.user_id,
            "template_title": self.template_title,
            "bureau": self.bureau,
            "method": self.method,
            "status": self.status,
            "email_status": self.email_status,
            "sendgrid_id": self.sendgrid_id,
            "delivery_ts": self.delivery_ts.isoformat(),
            "acknowledged_ts": (self.acknowledged_ts.isoformat() if self.acknowledged_ts else None),
            "badges": self.get_badges(),
            "dispatch_state": self.dispatch_state,
            "urls": {
                "txt": self.download_txt_url,
                "pdf": self.download_pdf_url,
                "zip": self.download_zip_url,
            },
        }
