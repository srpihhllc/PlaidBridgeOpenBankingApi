# =============================================================================
# FILE: app/forms/mfa_forms.py
# DESCRIPTION: MFA code entry form.
# =============================================================================

from flask_wtf import FlaskForm
from wtforms import StringField, SubmitField
from wtforms.validators import DataRequired, Length


class MFAForm(FlaskForm):
    code = StringField("MFA Code", validators=[DataRequired(), Length(min=6, max=10)])
    submit = SubmitField("Verify")


class MFAEnableForm(FlaskForm):
    code = StringField("Setup Code", validators=[DataRequired(), Length(min=6, max=10)])
    submit = SubmitField("Enable MFA")
