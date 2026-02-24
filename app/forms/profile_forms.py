# =============================================================================
# FILE: app/forms/profile_forms.py
# DESCRIPTION: User profile update form.
# =============================================================================

from flask_wtf import FlaskForm
from wtforms import StringField, SubmitField
from wtforms.validators import DataRequired, Length


class ProfileUpdateForm(FlaskForm):
    full_name = StringField("Full Name", validators=[DataRequired(), Length(max=120)])
    address = StringField("Address", validators=[Length(max=255)])
    submit = SubmitField("Update Profile")
