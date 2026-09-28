# /home/srpihhllc/PlaidBridgeOpenBankingApi/app/tests/test_warning_handling.py

import warnings
import pytest


# ==============================================================================
# SAMPLE FUNCTIONS (Representing system components emitting warnings)
# ==============================================================================
def legacy_api():
    """Triggers a DeprecationWarning."""
    warnings.warn(
        "legacy_api is deprecated, use v2_api instead", DeprecationWarning
    )
    return True


def sensitive_calculation(val):
    """Triggers a UserWarning for specific edge cases."""
    if val < 0:
        warnings.warn("Negative input detected, converting to absolute value", UserWarning)
        return abs(val)
    return val


# ==============================================================================
# 1. EXACT WARNING MATCHING (pytest.warns)
# ==============================================================================
def test_user_warning_explicit_match():
    """Asserts that a specific warning type AND message pattern are raised."""
    # Match using regex pattern
    with pytest.warns(UserWarning, match=r"Negative input detected"):
        result = sensitive_calculation(-5)
        assert result == 5


def test_inspect_recorded_warning_details():
    """Captures warnings and validates specific properties without guessing."""
    with pytest.warns(UserWarning) as record:
        sensitive_calculation(-10)

    # Validate exact count and properties of emitted warning
    assert len(record) == 1
    assert "converting to absolute value" in str(record[0].message)


# ==============================================================================
# 2. DEPRECATION TESTING (pytest.deprecated_call)
# ==============================================================================
def test_legacy_api_deprecation():
    """Ensures code explicitly triggers a DeprecationWarning."""
    with pytest.deprecated_call():
        legacy_api()


# ==============================================================================
# 3. RECORDING VIA FIXTURE (recwarn)
# ==============================================================================
def test_multiple_warnings_with_recwarn(recwarn):
    """Uses the recwarn fixture to inspect all warnings across a test."""
    sensitive_calculation(-1)
    legacy_api()

    # Verify total count
    assert len(recwarn) == 2

    # Pop and inspect a specific warning class
    user_warn = recwarn.pop(UserWarning)
    assert issubclass(user_warn.category, UserWarning)
    assert "Negative input" in str(user_warn.message)


# ==============================================================================
# 4. PREVENTING WARNING LEAKAGE & STRICT ENFORCEMENT
# ==============================================================================
@pytest.mark.filterwarnings("error")
def test_zero_warnings_allowed():
    """
    Fails if ANY warning is emitted during execution.
    Converts warnings into explicit errors for this test item.
    """
    result = sensitive_calculation(10)  # Safe input, no warnings
    assert result == 10


@pytest.mark.filterwarnings("ignore:Negative input detected")
def test_explicitly_ignored_warning():
    """Ignores specific expected warnings so they don't clutter output."""
    result = sensitive_calculation(-20)
    assert result == 20