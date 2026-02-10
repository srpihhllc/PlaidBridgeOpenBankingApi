import os


def generate_link_token():
    """Return a placeholder link token for Plaid integration."""
    return os.getenv("PLAID_LINK_TOKEN", "mock-link-token")
