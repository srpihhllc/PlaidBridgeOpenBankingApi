# =============================================================================
# FILE: app/utils/balance_state.py
# DESCRIPTION: Shared global state for account balance used in tests.
# =============================================================================

# A single shared float that persists across imports and pytest reloads.
account_balance = 0.0
