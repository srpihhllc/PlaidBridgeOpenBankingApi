# app/models.py

from app import db
from werkzeug.security import generate_password_hash, check_password_hash

# ✅ User Model
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(200), nullable=False)

    def set_password(self, password):
        """Hashes and stores the user's password."""
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        """Checks password against stored hash."""
        return check_password_hash(self.password_hash, password)

# ✅ Loan Agreement Model (Tracks AI Compliance & Account Locking)
class LoanAgreement(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    lender_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    borrower_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    terms = db.Column(db.Text, nullable=False)
    status = db.Column(db.String(20), default="active")
    ai_flagged = db.Column(db.Boolean, default=False)
    locked = db.Column(db.Boolean, default=False)  # ✅ NEW: Account locking field
    violation_count = db.Column(db.Integer, default=0)  # ✅ Tracks compliance violations

# ✅ Transaction Model (Monitors Fraud Detection)
class Transaction(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    amount = db.Column(db.Float, nullable=False)
    description = db.Column(db.String(200), nullable=False)
    ai_verified = db.Column(db.Boolean, default=False)

