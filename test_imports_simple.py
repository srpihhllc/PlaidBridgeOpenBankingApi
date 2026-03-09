#!/usr/bin/env python3
"""Simple import test without app creation."""
import sys
import os

os.environ["FLASK_ENV"] = "testing"
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

try:
    # Test the import that was failing
    print("Testing User model import...")
    from PlaidBridgeOpenBankingApi.app.models.user import User
    print(f"✅ User imported: tablename={User.__tablename__}, extend={User.__table_args__}")
    
    print("\nTesting AccessToken model import...")
    from PlaidBridgeOpenBankingApi.app.models.access_token import AccessToken
    print(f"✅ AccessToken imported: tablename={AccessToken.__tablename__}, extend={AccessToken.__table_args__}")
    
    print("\n🎉 All imports successful!")
    
except Exception as e:
    print(f"\n❌ Import failed: {type(e).__name__}: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)
