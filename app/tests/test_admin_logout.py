# /home/srpihhllc/PlaidBridgeOpenBankingApi/app/tests/test_admin_logout.py

def test_admin_delete_user_cascade_api(client):
    """
    DIAGNOSTIC RUN: Profile database visibility and user loader boundary.
    """
    import random
    import sys
    from flask_jwt_extended import create_access_token
    from werkzeug.security import generate_password_hash

    from app.extensions import db
    from app.models.plaid_item import PlaidItem
    from app.models.user import User

    admin_uuid = "TERENCE_CORTEX_PRIME"
    dummy_id = random.randint(10000, 99999)
    item_id = random.randint(10000, 99999)

    with client.application.app_context():
        # Clear any collisions
        User.query.filter_by(email="admin@example.com").delete()
        db.session.commit()

        # Clean Insert
        admin = User(
            id=admin_uuid,
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

        # Verify local visibility inside the setup context
        print("\n" + "="*50)
        print("[DIAGNOSTIC] DUMPING USERS IN APP_CONTEXT BEFORE REQUEST:")
        for u in User.query.all():
            print(f"  -> Found User Row | ID: {u.id} (Type: {type(u.id)}) | Email: {u.email}")
        print("="*50)

        token = create_access_token(
            identity=admin_uuid,
            additional_claims={"is_admin": True, "roles": ["admin"]},
        )

    headers = {"Authorization": f"Bearer {token}"}

    # Execute request
    response = client.delete(
        f"/admin/api/v1/users/{dummy_id}",
        headers=headers,
    )

    # If it still fails, drop directly into the live shell context to inspect variables
    if response.status_code == 401:
        print("\n❌ 401 DETECTED. DROPPING TO INTERACTIVE DEBUGGER...")
        print(f"Response Body: {response.get_data(as_text=True)}")
        # breakpoint()  # Python 3.7+ native debugger. Type 'c' to exit, or inspect variables.

    assert response.status_code in [200, 204]