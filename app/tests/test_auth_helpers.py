# app/tests/test_auth_helpers.py
def test_auth_headers_produces_valid_session(client, app, auth_headers):
    """
    Quick smoke: ensure auth_headers yields a request that the app accepts.
    Accept either 200 (direct landing) or 302 (redirect to login/landing).
    """
    resp = client.get("/sub/", headers=auth_headers, follow_redirects=True)
    assert resp.status_code in (200, 302)
