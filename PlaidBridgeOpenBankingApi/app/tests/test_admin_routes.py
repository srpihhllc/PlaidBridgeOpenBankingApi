# /home/srpihhllc/PlaidBridgeOpenBankingApi/app/tests/test_admin_routes.py

from flask_jwt_extended import create_access_token


def test_admin_access_required(client):
    """Ensure non-admins are blocked from admin routes."""
    user_id = "999"
    user_email = "regular_tester@example.com"

    with client.application.app_context():
        from app.extensions import db
        from app.models.user import User

        test_user = User.query.filter_by(id=user_id).first()
        if not test_user:
            test_user = User(
                id=user_id,
                username="regular_tester",  # Add this to satisfy NOT NULL
                email=user_email,
                password_hash="mock_hash_str",  # Satisfies the constraint you hit
                is_admin=False,
            )
            db.session.add(test_user)
            db.session.commit()

        access_token = create_access_token(identity=user_id, additional_claims={"is_admin": False})

    headers = {"Authorization": f"Bearer {access_token}"}
    response = client.get("/admin/api/v1/users", headers=headers)

    # Result: The user exists (200-level auth) but lacks admin (403-level auth)
    assert response.status_code == 403


def test_admin_delete_user_cascade_api(client):
    """
    Ensure an admin (authenticated via JWT) can delete a user
    and cascade-delete the user's PlaidItem.
    """
    import random

    from flask_jwt_extended import create_access_token
    from werkzeug.security import generate_password_hash

    from app.extensions import db
    from app.models.plaid_item import PlaidItem
    from app.models.user import User

    # ---------------------------------------------------------
    # 1. SETUP: Create dummy user + linked PlaidItem + Ensure Admin Exists
    # ---------------------------------------------------------
    dummy_id = random.randint(10000, 99999)
    item_id = random.randint(10000, 99999)

    with client.application.app_context():
        # Ensure admin user exists in test DB
        admin = User.query.filter_by(email="admin@example.com").first()
        if not admin:
            admin = User(
                id=1,  # Set explicit integer ID for JWT compatibility
                username="admin_user",
                email="admin@example.com",
                password_hash=generate_password_hash("AdminPass123!"),
                is_admin=True,
                role="admin",
                is_approved=True,
                is_mfa_enabled=False,
            )
            db.session.add(admin)

        dummy_user = User(
            id=dummy_id,
            username=f"delete_me_{dummy_id}",
            email=f"temp_{dummy_id}@test.com",
            password_hash="nosync",
            is_admin=False,
        )
        db.session.add(dummy_user)

        item = PlaidItem(
            id=item_id,
            user_id=dummy_id,
            plaid_item_id=f"test_item_{item_id}",
            access_token="test_tok",
        )
        db.session.add(item)
        db.session.commit()

        # ---------------------------------------------------------
        # 2. AUTH: Create a valid ADMIN JWT
        # ---------------------------------------------------------
        token = create_access_token(
            identity=str(admin.id),
            additional_claims={"is_admin": True, "roles": ["admin"]},
        )

    headers = {"Authorization": f"Bearer {token}"}

    # ---------------------------------------------------------
    # 3. ACTION: Delete the dummy user via the ADMIN API
    # ---------------------------------------------------------
    response = client.delete(
        f"/admin/api/v1/users/{dummy_id}",
        headers=headers,
    )

    assert response.status_code in [200, 204], (
        f"Expected 200/204, got {response.status_code}. "
        f"Response: {response.get_data(as_text=True)}"
    )

    # ---------------------------------------------------------
    # 4. VERIFY: User + PlaidItem were cascade-deleted
    # ---------------------------------------------------------
    with client.application.app_context():
        db.session.expunge_all()

        assert User.query.get(dummy_id) is None, "User was not deleted"
        assert (
            PlaidItem.query.filter_by(user_id=dummy_id).first() is None
        ), "PlaidItem was not cascade-deleted"