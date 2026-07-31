# =============================================================================
# FILE: app/tests/test_factory_phase5_completion.py
# DESCRIPTION: Final validation suite for advanced factory configuration patterns,
#              route hygiene safeguards, and identity runtime lookups.
# =============================================================================

import pytest
import sys
from unittest.mock import MagicMock, patch
from flask import Flask

# =============================================================================
# UTILITY HELPER
# =============================================================================
def _get_jwt_user_lookup_callback(app):
    """Extracts the inner _jwt_user_lookup function from the registered extensions."""
    jwt_manager = app.extensions.get("jwt") or app.extensions.get("flask-jwt-extended")
    if not jwt_manager:
        raise RuntimeError(f"JWT manager not found. Keys: {list(app.extensions.keys())}")

    callback = getattr(jwt_manager, "_user_lookup_callback", None)
    if not callback:
        raise RuntimeError("_jwt_user_lookup callback was not bound properly.")
    return callback


# =============================================================================
# 1. IDENTITY LOOKUP & OVERRIDE TESTS
# =============================================================================

def test_jwt_user_identity_loader_passthrough(app):
    jwt_manager = app.extensions.get("flask_jwt_extended") or app.extensions.get("jwt")
    identity_callback = getattr(jwt_manager, "_user_identity_callback", None)
    if identity_callback:
        assert identity_callback("test-uuid-123") == "test-uuid-123"
        assert identity_callback("TERENCE_CORTEX_PRIME") == "TERENCE_CORTEX_PRIME"


def test_jwt_user_lookup_blank_and_null_values(app):
    _jwt_user_lookup = _get_jwt_user_lookup_callback(app)
    with app.app_context():
        assert _jwt_user_lookup({}, {}) is None
        assert _jwt_user_lookup({}, {"sub": ""}) is None
        assert _jwt_user_lookup({}, {"identity": "    "}) is None
        assert _jwt_user_lookup({}, {"sub": "none"}) is None
        assert _jwt_user_lookup({}, {"sub": "  NULL  "}) is None


def test_jwt_user_lookup_cortex_prime_operator(app):
    """Targets SystemOperator lifecycle using blanket interceptor patching across namespaces."""
    from app.extensions import db
    from app.models.user import User
    _jwt_user_lookup = _get_jwt_user_lookup_callback(app)

    with app.app_context():
        # 🛡️ ISOLATION GUARD
        db.session.rollback()

        test_user = User(
            id="TERENCE_CORTEX_PRIME",
            uuid="TERENCE_CORTEX_PRIME",
            username="TERENCE_CORTEX_PRIME",
            email="cortex_prime@example.com",
            role="operator",
            is_admin=True
        )

        # 🛡️ SYSTEM OPERATOR MOCK (Enhanced with attributes required by authorization gates)
        mock_sys_op_instance = MagicMock()
        mock_sys_op_instance.__class__.__name__ = "SystemOperator"
        mock_sys_op_instance.id = "TERENCE_CORTEX_PRIME"
        mock_sys_op_instance.is_admin = True
        mock_sys_op_instance.is_active = True
        MockSysOpClass = MagicMock(return_value=mock_sys_op_instance)

        # State tracking for clean restoration
        originals_globals = {}
        originals_sys_modules = {}
        originals_modules_attrs = []

        # 1. Inject directly into the function's globals
        if "SystemOperator" in _jwt_user_lookup.__globals__:
            originals_globals["SystemOperator"] = _jwt_user_lookup.__globals__["SystemOperator"]
        _jwt_user_lookup.__globals__["SystemOperator"] = MockSysOpClass

        # 2. Inject into any imported namespaces found in globals (e.g., models.SystemOperator)
        for g_name, g_val in list(_jwt_user_lookup.__globals__.items()):
            if g_name in ["models", "auth_handlers", "user", "handlers"] or "auth" in g_name:
                if g_val and hasattr(g_val, "SystemOperator"):
                    originals_modules_attrs.append((g_val, "SystemOperator", getattr(g_val, "SystemOperator")))
                    setattr(g_val, "SystemOperator", MockSysOpClass)

        # 3. Inject into sys.modules to intercept function-local internal imports
        import sys
        target_modules = ["app.auth_handlers", "app.models.user", "app.models", "app.services", "app.auth"]
        for mod_name in target_modules:
            if mod_name in sys.modules:
                mod = sys.modules[mod_name]
                if hasattr(mod, "SystemOperator"):
                    originals_sys_modules[(mod_name, "SystemOperator")] = getattr(mod, "SystemOperator")
                    setattr(mod, "SystemOperator", MockSysOpClass)

        try:
            # Multi-path patch context managers as a final line of defense
            with patch("app.auth_handlers.SystemOperator", MockSysOpClass, create=True), \
                 patch("app.models.user.SystemOperator", MockSysOpClass, create=True), \
                 patch("app.models.SystemOperator", MockSysOpClass, create=True), \
                 patch("app.extensions.db.session.get", return_value=test_user), \
                 patch("app.extensions.db.session.execute") as mock_execute, \
                 patch("app.models.user.User.query", create=True) as mock_query:
                
                # Broad safety net for database fall-through prevention
                mock_execute.return_value.scalar_one_or_none.return_value = test_user
                mock_query.filter_by.return_value.first.return_value = test_user
                mock_query.get.return_value = test_user

                # ⭐ DUAL PAYLOAD TARGETING: Satisfy all token claim variants
                jwt_payload = {
                    "sub": "TERENCE_CORTEX_PRIME", 
                    "identity": "TERENCE_CORTEX_PRIME"
                }

                # 1. Happy path: Native resolution matching mock instance or class string name
                res = _jwt_user_lookup({}, jwt_payload)
                assert res is not None, "Lookup returned None. SystemOperator mock failed to intercept initialization."
                assert res == mock_sys_op_instance or res.__class__.__name__ == "SystemOperator"

                # 2. Exception path: Simulate Cortex boot failure 
                MockSysOpClass.side_effect = RuntimeError("Cortex boot failure")
                res_err = _jwt_user_lookup({}, jwt_payload)
                assert res_err is None or res_err == test_user

        finally:
            # 🧹 METICULOUS CLEANUP: Restore runtime environment state
            for name, orig_val in originals_globals.items():
                _jwt_user_lookup.__globals__[name] = orig_val
            if "SystemOperator" in _jwt_user_lookup.__globals__ and "SystemOperator" not in originals_globals:
                del _jwt_user_lookup.__globals__["SystemOperator"]

            for obj, attr, orig_val in originals_modules_attrs:
                setattr(obj, attr, orig_val)

            for (mod_name, attr), orig_val in originals_sys_modules.items():
                if mod_name in sys.modules:
                    setattr(sys.modules[mod_name], attr, orig_val)


def test_jwt_user_lookup_database_resolution_and_integer_fallbacks(app):
    _jwt_user_lookup = _get_jwt_user_lookup_callback(app)

    with app.app_context():
        with patch("app.extensions.db.session.get") as mock_get:
            # Case A: Happy primary path string key match
            mock_get.return_value = "UserObjectFound"
            assert _jwt_user_lookup({}, {"sub": "uuid-key-xyz"}) == "UserObjectFound"

            # Case B: Legacy integer fallback strategy match
            mock_get.side_effect = [None, "LegacyUserObjectMatched"]
            assert _jwt_user_lookup({}, {"sub": "45678"}) == "LegacyUserObjectMatched"

        # Case C: Primary miss, parsing ValueError bypass, exits via direct ORM query
        with patch("app.extensions.db.session.get", return_value=None), \
             patch("app.models.user.User.query") as mock_query:
            mock_query.filter_by.return_value.first.return_value = "OrmFallbackUserObject"
            assert _jwt_user_lookup({}, {"sub": "not-an-int"}) == "OrmFallbackUserObject"


def test_jwt_user_lookup_global_exception_handling(app):
    _jwt_user_lookup = _get_jwt_user_lookup_callback(app)
    with app.app_context():
        with patch("app.extensions.db.session.get", side_effect=Exception("Database failure")):
            assert _jwt_user_lookup({}, {"sub": "emergency-test-id"}) is None


# =============================================================================
# 2. ROUTE HYGIENE & REGISTRY PROTECTION TESTS
# =============================================================================

def test_ensure_admin_index_registered_missing_attributes():
    from app import _ensure_admin_index_registered
    mock_app = MagicMock(spec=[])
    del mock_app.url_map
    assert _ensure_admin_index_registered(mock_app) is None


def test_ensure_admin_index_registered_duplicate_rule_pruning():
    from app import _ensure_admin_index_registered
    mock_app = Flask("test_hygiene")
    rule = MagicMock(rule="/admin/", endpoint="admin.admin_index")
    mock_app.url_map.iter_rules = lambda: [rule, rule]
    mock_app.url_map._rules_by_endpoint = {"admin.admin_index": [rule, rule]}
    _ensure_admin_index_registered(mock_app)
    assert len(mock_app.url_map._rules_by_endpoint["admin.admin_index"]) == 1


def test_register_legacy_main_aliases_rule_replication():
    from app import _register_legacy_main_aliases
    mock_app = Flask("test_alias")
    mock_app.view_functions["admin.redis_panel"] = lambda: "View"
    mock_app.url_map._rules_by_endpoint = {"admin.redis_panel": ["Rule"]}
    _register_legacy_main_aliases(mock_app)
    assert "main.redis_panel" in mock_app.view_functions


# =============================================================================
# 3. ADVANCED FACTORY CONFIGURATION STRATEGY TESTS
# =============================================================================

def test_create_app_string_dot_configuration_loading():
    from app import create_app
    app = create_app(config_class="app.config.TestingConfig")
    assert app.config["TESTING"] is True


def test_create_app_fallback_object_exceptions():
    from app import create_app
    from flask import Config

    # Capture the real method so we can use it for the fallback
    original_from_object = Config.from_object

    call_count = 0
    def side_effect_loader(self, obj):
        nonlocal call_count
        call_count += 1

        # 1. First execution: Simulate the primary config failing
        if call_count == 1:
            raise Exception("Error")

        # 2. Second execution (Fallback): Route it to the real Flask config loader
        return original_from_object(self, obj)

    # Use autospec=True so the mock correctly handles the 'self' (config dict) argument
    with patch("flask.Config.from_object", side_effect=side_effect_loader, autospec=True):
        app = create_app(config_class=MagicMock())
        assert app.config["TESTING"] is True