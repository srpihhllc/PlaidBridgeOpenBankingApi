# app/tests/models/test_subscriber_profile.py

from app.models.subscriber_profile import SubscriberProfile, Subscription
from app.models.user import User


def make_user(**values):
    defaults = {
        "id": "user-123",
        "username": "alice",
        "ssn_last4": "1234",
        "routing_number": "021000021",
        "account_ending": "6789",
    }
    defaults.update(values)
    return User(**defaults)


def test_subscription_repr():
    sub = Subscription()
    sub.id = 10
    sub.status = "active"

    assert repr(sub) == "<Subscription id=10 status=active>"


def test_set_password_delegates_to_user(monkeypatch):
    profile = SubscriberProfile()
    user = make_user()
    profile.user = user

    calls = []

    def fake_set_password(password):
        calls.append(password)

    monkeypatch.setattr(user, "set_password", fake_set_password)

    profile.set_password("secret-password")

    assert calls == ["secret-password"]


def test_set_password_does_nothing_without_user():
    profile = SubscriberProfile()

    assert profile.user is None
    assert profile.set_password("secret-password") is None


def test_check_password_delegates_to_user(monkeypatch):
    profile = SubscriberProfile()
    user = make_user()
    profile.user = user

    calls = []

    def fake_check_password(password):
        calls.append(password)
        return password == "secret-password"

    monkeypatch.setattr(user, "check_password", fake_check_password)

    assert profile.check_password("secret-password") is True
    assert profile.check_password("wrong-password") is False
    assert calls == ["secret-password", "wrong-password"]


def test_check_password_returns_false_without_user():
    profile = SubscriberProfile()

    assert profile.user is None
    assert profile.check_password("secret-password") is False


def test_generate_api_key():
    profile = SubscriberProfile()

    profile.generate_api_key()

    assert profile.api_key is not None
    assert len(profile.api_key) == 64


def test_is_verified_when_identity_data_is_complete():
    profile = SubscriberProfile()
    profile.user = make_user()

    assert profile.is_verified is True


def test_is_verified_when_identity_data_is_incomplete():
    profile = SubscriberProfile()
    profile.user = make_user(routing_number=None)

    assert profile.is_verified is False


def test_is_verified_without_user():
    profile = SubscriberProfile()

    assert profile.user is None
    assert profile.is_verified is False


def test_identity_tip_with_complete_identity_data():
    profile = SubscriberProfile()
    profile.user = make_user()

    assert profile.identity_tip == (
        "alice • SSN●●●1234 • ACCT●●●6789"
    )


def test_identity_tip_uses_masks_for_missing_values():
    profile = SubscriberProfile()
    profile.user = make_user(
        ssn_last4=None,
        account_ending=None,
    )

    assert profile.identity_tip == (
        "alice • SSN●●●---- • ACCT●●●----"
    )


def test_identity_tip_without_user():
    profile = SubscriberProfile()

    assert profile.user is None
    assert profile.identity_tip == "No User Linked"


def test_subscriber_profile_repr():
    profile = SubscriberProfile()
    profile.id = 7
    profile.user_id = "user-123"

    assert repr(profile) == "<SubscriberProfile id=7 user_id=user-123>"