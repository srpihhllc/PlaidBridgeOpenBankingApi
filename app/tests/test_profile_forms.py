# /home/srpihhllc/PlaidBridgeOpenBankingApi/app/tests/test_profile_forms.py


from app import create_app
from app.forms.profile_forms import ProfileUpdateForm


def test_profile_update_form_validation():
    """Verify that ProfileUpdateForm validates correctly using unit-test friendly meta-data."""

    app = create_app()

    with app.app_context():
        # 1. Test valid submission
        # We pass meta={'csrf': False} to bypass the requirement for a request session
        valid_form = ProfileUpdateForm(
            data={"full_name": "Jane Doe", "address": "123 Tech Lane"},
            meta={"csrf": False},
        )
        assert valid_form.validate() is True

        # 2. Test invalid submission (triggering DataRequired)
        invalid_form = ProfileUpdateForm(
            data={"full_name": ""}, meta={"csrf": False}
        )
        assert invalid_form.validate() is False
        assert "full_name" in invalid_form.errors

        # 3. Test Length validation (address max 255)
        long_address_form = ProfileUpdateForm(
            data={"full_name": "Jane Doe", "address": "a" * 256},
            meta={"csrf": False},
        )
        assert not long_address_form.validate()
        assert "address" in long_address_form.errors
