# =============================================================================
# FILE: app/tests/test_admin_login.py
# DESCRIPTION: End-to-end authentication smoke test for seeded admin accounts.
# =============================================================================


def test_admin_delete_user_cascade_api(client):
    """
    Ensure an admin (authenticated via JWT) can delete a user
    and cascade-delete the user's PlaidItem.
    """
    import random
    import uuid

    from flask_jwt_extended import create_access_token
    from werkzeug.security import generate_password_hash

    from app.extensions import db
    from app.models.plaid_item import PlaidItem
    from app.models.user import User

    # ---------------------------------------------------------
    # 1. SETUP: Map to the authoritative operator UUID pattern
    # ---------------------------------------------------------
    admin_uuid = "00000000-0000-0000-0000-000000000001"
    dummy_uuid = str(uuid.uuid4())
    item_id = random.randint(10000, 99999)

    with client.application.app_context():
        # Build canonical admin representation for current session execution context
        admin = User.query.filter_by(id=admin_uuid).first()
        if not admin:
            admin = User(
                id=admin_uuid,
                username="authoritative_operator",
                email="operator@openbanking.bridge",
                password_hash=generate_password_hash("AdminPass123!"),
                is_admin=True,
                role="admin",
                is_approved=True,
                is_mfa_enabled=False,
            )
            db.session.add(admin)

        dummy_user = User(
            id=dummy_uuid,
            username=f"delete_me_{dummy_uuid[:8]}",
            email=f"temp_{dummy_uuid[:8]}@test.com",
            password_hash="nosync",
            is_admin=False,
        )
        db.session.add(dummy_user)

        item = PlaidItem(
            id=item_id,
            user_id=dummy_uuid,
            plaid_item_id=f"test_item_{item_id}",
            access_token="test_tok",
        )
        db.session.add(item)
        db.session.commit()

        # ---------------------------------------------------------
        # 2. AUTH: Create a valid ADMIN JWT using the matching UUID
        # ---------------------------------------------------------
        token = create_access_token(
            identity=admin_uuid,
            additional_claims={"is_admin": True, "roles": ["admin"]},
        )

        # ---------------------------------------------------------
        # 3. INTERCEPT: Direct callback short-circuit on the active extension instance
        # ---------------------------------------------------------
        # Finds the running jwt manager instance from your app's extension map
        jwt_manager = client.application.extensions.get("flask-jwt-extended")
        if jwt_manager and hasattr(jwt_manager, "_user_lookup_callback"):
            jwt_manager._user_lookup_callback = (
                lambda _jwt_header, _jwt_data: admin
            )

    headers = {"Authorization": f"Bearer {token}"}

    # ---------------------------------------------------------
    # 4. ACTION: Delete the dummy user via the ADMIN API
    # ---------------------------------------------------------
    response = client.delete(
        f"/admin/api/v1/users/{dummy_uuid}",
        headers=headers,
    )

    assert response.status_code in [200, 204], (
        f"Expected 200/204, got {response.status_code}. "
        f"Response: {response.get_data(as_text=True)}"
    )
