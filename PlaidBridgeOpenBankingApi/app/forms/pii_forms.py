# /home/srpihhllc/PlaidBridgeOpenBankingApi/app/forms/pii_forms.py

from flask_wtf import FlaskForm
from wtforms import PasswordField, SubmitField
from wtforms.validators import DataRequired


class PIIRequestForm(FlaskForm):
    password = PasswordField("Password", validators=[DataRequired()])
    submit = SubmitField("Request PII Export")
