# /home/srpihhllc/PlaidBridgeOpenBankingApi/app/tests/early_redis_stub.py
# =============================================================================
# EARLY REDIS STUB — runs BEFORE conftest, BEFORE app imports, BEFORE create_app
# =============================================================================


def pytest_load_initial_conftests(early_config, parser, args):
    """
    This hook runs BEFORE pytest imports the app package.
    This is the ONLY place where we can guarantee Redis is stubbed early enough.
    """
    import app.utils.redis_utils as redis_utils
    from app.tests.utils.dummies import DummyRedis

    dummy = DummyRedis()
    redis_utils.get_redis_client = lambda: dummy

    if redis_utils.get_redis_client() is not dummy:
        raise RuntimeError("Early Redis stub failed to install.")
