#!/usr/bin/env python3
"""
Quick test to verify model import aliasing prevents duplicate table registration.
Run this before pushing to CI to catch import issues early.
"""
import sys
import os

os.environ["FLASK_ENV"] = "testing"
os.environ["TESTING"] = "1"

# Simulate what Alembic does
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

try:
    # Import via the PlaidBridgeOpenBankingApi path (like CI does)
    from PlaidBridgeOpenBankingApi.app import create_app
    from PlaidBridgeOpenBankingApi.app.extensions import db
    import PlaidBridgeOpenBankingApi.app.models  # noqa
    
    print("✅ Step 1: Imported via PlaidBridgeOpenBankingApi.app path")
    
    # Now try importing via the `app` alias (like blueprints/routes do)
    from app.models.user import User
    from app.models import Transaction
    
    print("✅ Step 2: Imported via app.models alias")
    
    # Create app and check metadata
    app = create_app(env_name="testing")
    
    with app.app_context():
        # Try to access User table - should not raise InvalidRequestError
        from sqlalchemy import inspect
        inspector = inspect(db.engine)
        tables = inspector.get_table_names()
        
        print(f"✅ Step 3: App created, {len(tables)} tables in metadata")
        
        # Verify User model is accessible
        user_table = User.__table__
        print(f"✅ Step 4: User table name: {user_table.name}")
        
        # Check that app.models.user and PlaidBridgeOpenBankingApi.app.models.user are the same
        import app.models.user as alias_user_mod
        import PlaidBridgeOpenBankingApi.app.models.user as canonical_user_mod
        
        if alias_user_mod is canonical_user_mod:
            print("✅ Step 5: Module aliasing working - app.models.user === PlaidBridgeOpenBankingApi.app.models.user")
        else:
            print("❌ Step 5: FAILED - modules are different objects!")
            sys.exit(1)
        
    print("\n" + "="*70)
    print("🎉 SUCCESS: All checks passed! Model import safety is working.")
    print("="*70)
    
except Exception as e:
    print(f"\n❌ FAILED: {type(e).__name__}: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)
