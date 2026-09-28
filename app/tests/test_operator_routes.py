# =============================================================================
# FILE: app/tests/test_operator_routes.py
# DESCRIPTION: Regression tests verifying operator endpoint security & method gating.
# =============================================================================

import pytest

MUTATION_PATHS = [
    "/api/operator/enable",
    "/api/operator/toggle-mode",
    "/api/operator/disable",
    "/api/operator/force_template_audit",
]


@pytest.mark.parametrize("path", MUTATION_PATHS)
def test_operator_mutations_reject_get_requests(client, path):
    """Verify state-changing endpoints return 405 Method Not Allowed on GET."""
    response = client.get(path, follow_redirects=False)
    assert response.status_code == 405


@pytest.mark.parametrize("path", MUTATION_PATHS)
def test_operator_mutations_require_authentication(client, path):
    """Verify unauthenticated POST requests are rejected (400/401/403/302)."""
    response = client.post(path, follow_redirects=False)
    assert response.status_code in {400, 401, 403, 302}


def test_operator_debug_flags_get_and_post_behavior(client, auth_headers):
    """Verify /api/operator/debug_flags allows GET (inspect) and guards POST (mutate)."""
    # Unauthenticated GET
    res_get = client.get("/api/operator/debug_flags")
    assert res_get.status_code in {400, 401, 403}

    # Unauthenticated POST
    res_post = client.post("/api/operator/debug_flags", json={"DEBUG_TEST": True})
    assert res_post.status_code in {400, 401, 403}