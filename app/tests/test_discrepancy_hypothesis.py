# app/tests/test_discrepancy_hypothesis.py
from copy import deepcopy

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from app.services.discrepancy import correct_discrepancies

# --- 1) STRATEGIES FOR 'amount' FIELD ---

# Invalid inputs: None, malformed strings, arbitrary objects that can't
# be cast to float.
invalid_amount_st = st.one_of(
    st.none(),
    st.just("not_a_number"),
    st.just("10.5.0"),
    st.just("50 USD"),
    # Strings that contain at least one character outside [0-9.-]
    st.text(
        alphabet=st.characters(blacklist_characters="-.0123456789", min_codepoint=33),
        min_size=1,
    ),
    st.lists(st.integers(), max_size=3),  # complex types
)

# Valid inputs: integers, floats, or decimal strings with up to two places.
valid_amount_st = st.one_of(
    st.integers(min_value=-(10**6), max_value=10**6),
    st.floats(min_value=-1e6, max_value=1e6, allow_nan=False, allow_infinity=False),
    st.from_regex(r"^-?\d+(\.\d{1,2})?$", fullmatch=True),
)


# --- 2) STATEMENT RECORD STRATEGY ---
def statement_record_strategy():
    # Generate random dicts with at least one non-'amount' key
    other_keys = st.dictionaries(
        keys=st.text(min_size=1, max_size=8).filter(lambda s: s != "amount"),
        values=st.text(min_size=0, max_size=8),
        min_size=1,
        max_size=4,
    )
    # Then optionally inject an 'amount' key with either valid or invalid data
    return st.builds(
        lambda base, amt: {**base, **({"amount": amt} if amt is not None else {})},
        base=other_keys,
        amt=st.one_of(invalid_amount_st, valid_amount_st, st.none()),
    )


statements_list_st = st.lists(statement_record_strategy(), max_size=50)


@settings(max_examples=200)
@given(statements=statements_list_st)
def test_discrepancy_correction_invariants(statements):
    """
    Property-based test for correct_discrepancies.

    Invariants:
      1. Output list length == input list length.
      2. All non-'amount' keys are preserved verbatim.
      3. Every 'amount' in the output can be cast to float.
      4. No extra keys are injected.
    """
    # Deep copy to compare against original
    original = deepcopy(statements)
    corrected = correct_discrepancies(deepcopy(statements))

    # 1) Same number of records
    assert len(corrected) == len(original)

    for orig_rec, corr_rec in zip(original, corrected, strict=False):
        # 2) All original non-amount keys should match exactly
        for key, val in orig_rec.items():
            if key != "amount":
                assert corr_rec.get(key) == val

        # 3) If 'amount' exists, it must be float-convertible
        if "amount" in corr_rec:
            try:
                # float() accepts numeric types and numeric strings
                float(corr_rec["amount"])
            except (ValueError, TypeError):
                pytest.fail(f"Non-convertible amount {corr_rec['amount']!r} for record {orig_rec}")

        # 4) No new keys beyond those in orig_rec or 'amount'
        allowed_keys = set(orig_rec.keys()) | {"amount"}
        assert set(corr_rec.keys()) <= allowed_keys
