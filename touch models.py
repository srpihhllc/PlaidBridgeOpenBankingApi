from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(200), nullable=False)

    def __repr__(self):
        return f'<User {self.username}>'

class LoanAgreement(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    lender_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    borrower_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    terms = db.Column(db.Text, nullable=False)
    status = db.Column(db.String(20), default="active")
    ai_flagged = db.Column(db.Boolean, default=False)
    locked = db.Column(db.Boolean, default=False)
    violation_count = db.Column(db.Integer, default=0)

    def __repr__(self):
        return f'<LoanAgreement {self.id}>'

class Transaction(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    amount = db.Column(db.Float, nullable=False)
    description = db.Column(db.String(200), nullable=False)
    ai_verified = db.Column(db.Boolean, default=False)

    def __repr__(self):
        return f'<Transaction {self.id}>'
