#/home/srpihhllc/PlaidBridgeOpenBankingApi/app/tests/test_operator_cortex.py

from types import SimpleNamespace

import pytest

from app.operator_cortex import OperatorCortex


# ----------------------------------------------------------------------
# Constructor & Extensions Initialization Tests
# ----------------------------------------------------------------------

def test_constructor_without_app_starts_disabled():
    cortex = OperatorCortex()

    assert cortex.app is None
    assert cortex.is_enabled is False
    assert cortex.status() == {
        "status": "ok",
        "enabled": False,
        "message": "Operator Cortex subsystem placeholder",
    }


def test_constructor_with_app_initializes_extension():
    app = SimpleNamespace(
        extensions={},
        config={},
        logger=SimpleNamespace(info=lambda message: None),
    )

    cortex = OperatorCortex(app)

    assert cortex.app is app
    assert app.extensions["operator_cortex"] is cortex
    assert cortex.is_enabled is False


def test_init_app_creates_extensions_dict_when_missing():
    app = SimpleNamespace(
        config={},
        logger=SimpleNamespace(info=lambda message: None),
    )

    cortex = OperatorCortex()
    cortex.init_app(app)

    assert isinstance(app.extensions, dict)
    assert app.extensions["operator_cortex"] is cortex
    assert cortex.app is app


def test_init_app_replaces_non_dict_extensions():
    app = SimpleNamespace(
        extensions=SimpleNamespace(),
        config={},
        logger=SimpleNamespace(info=lambda message: None),
    )

    cortex = OperatorCortex(app)

    assert isinstance(app.extensions, dict)
    assert app.extensions["operator_cortex"] is cortex


# ----------------------------------------------------------------------
# Configuration & Coercion Tests
# ----------------------------------------------------------------------

@pytest.mark.parametrize(
    ("config_value", "expected"),
    [
        (True, True),
        (False, False),
        ("yes", True),
        (0, False),
    ],
)
def test_enabled_configuration_is_coerced_to_bool(config_value, expected):
    app = SimpleNamespace(
        extensions={},
        config={"OPERATOR_CORTEX_ENABLED": config_value},
        logger=SimpleNamespace(info=lambda message: None),
    )

    cortex = OperatorCortex(app)

    assert cortex.is_enabled is expected


# ----------------------------------------------------------------------
# Logger Fallback Tests
# ----------------------------------------------------------------------

def test_init_app_uses_module_logger_when_app_has_no_logger(caplog):
    app = SimpleNamespace(
        extensions={},
        config={},
    )

    cortex = OperatorCortex()

    with caplog.at_level("INFO", logger="app.operator_cortex"):
        cortex.init_app(app)

    assert cortex.app is app
    assert app.extensions["operator_cortex"] is cortex
    assert "OperatorCortex initialized successfully." in caplog.text


# ----------------------------------------------------------------------
# State Transitions & Status Tests
# ----------------------------------------------------------------------

def test_enable_and_disable():
    cortex = OperatorCortex()

    cortex.enable()
    assert cortex.is_enabled is True
    assert cortex.status()["enabled"] is True

    cortex.disable()
    assert cortex.is_enabled is False
    assert cortex.status()["enabled"] is False