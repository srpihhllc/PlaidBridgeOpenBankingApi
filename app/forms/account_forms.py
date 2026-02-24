# /home/srpihhllc/PlaidBridgeOpenBankingApi/app/forms/account_forms.py

from flask_wtf import FlaskForm
from wtforms import StringField, SubmitField
from wtforms.validators import DataRequired, Length


class AccountUpdateForm(FlaskForm):
    first_name = StringField("First Name", validators=[DataRequired(), Length(max=50)])
    last_name = StringField("Last Name", validators=[DataRequired(), Length(max=50)])
    address = StringField("Address", validators=[Length(max=255)])
    city = StringField("City", validators=[Length(max=100)])
    state = StringField("State", validators=[Length(max=50)])
    zip_code = StringField("Zip Code", validators=[Length(max=20)])
    submit = SubmitField("Update Account")
