# name=app/tests/test_route_sentinel.py


def _rules_for(app, path: str):
    """Return list of werkzeug.routing.Rule objects matching an exact path or endpoint."""
    return [
        r
        for r in app.url_map.iter_rules()
        if r.rule == path or r.endpoint == path
    ]


def _endpoints_of(rules):
    return {r.endpoint for r in rules}


def _assert_owned_by_oauth(rules):
    eps = _endpoints_of(rules)
    assert eps, "No endpoints found for rule(s)"
    # Ensure every endpoint is owned by oauth blueprint
    assert all(e.startswith("oauth.") for e in eps), (
        "Found non-oauth endpoint(s) for the rule: " + ", ".join(sorted(eps))
    )
    # Ensure blueprint name set is exactly {'oauth'}
    bps = {e.split(".", 1)[0] for e in eps}
    assert bps == {
        "oauth"
    }, f"Expected only 'oauth' blueprint ownership; found: {bps}"


def test_oauth_callback_google_sentinel(app, client):
    """
    Sentinel for /callback/google:
    - exact rule exists
    - owned by oauth blueprint (endpoint names start with 'oauth.')
    - explicit clean endpoint present
    - GET without code returns 400 and expected message
    """
    rules = _rules_for(app, "/callback/google")
    assert rules, "No rule registered for /callback/google"

    endpoints = _endpoints_of(rules)
    # Match against the exact runtime endpoint registered by the app
    assert (
        "oauth.callback_google" in endpoints
    ), f"Expected 'oauth.callback_google' to be registered for /callback/google; found: {sorted(endpoints)}"

    # Ensure no other blueprint is shadowing this rule
    _assert_owned_by_oauth(rules)

    # Behavior: missing code → 400 and contains the missing-code message
    resp = client.get("/callback/google")
    assert (
        resp.status_code == 400
    ), f"Expected 400 for missing code, got {resp.status_code}"
    body = resp.get_data(as_text=True) or ""
    assert (
        "missing code" in body.lower()
    ), "Response did not include expected missing-code message"


def test_oauth_callback_microsoft_sentinel(app, client):
    """
    Sentinel for /callback/microsoft:
    - exact rule exists
    - owned by oauth blueprint
    - explicit clean endpoint present
    - GET without code returns 400 and expected message
    """
    rules = _rules_for(app, "/callback/microsoft")
    assert rules, "No rule registered for /callback/microsoft"

    endpoints = _endpoints_of(rules)
    # Match against the exact runtime endpoint registered by the app
    assert (
        "oauth.callback_microsoft" in endpoints
    ), f"Expected 'oauth.callback_microsoft' to be registered for /callback/microsoft; found: {sorted(endpoints)}"

    _assert_owned_by_oauth(rules)

    resp = client.get("/callback/microsoft")
    assert (
        resp.status_code == 400
    ), f"Expected 400 for missing code, got {resp.status_code}"
    body = resp.get_data(as_text=True) or ""
    assert (
        "missing code" in body.lower()
    ), "Response did not include expected missing-code message"


def test_oauth_callback_provider_and_oauth_prefix_sentinel(app):
    """
    Sentinel for the parameterized provider route:
    - a rule exists for the dynamic callback endpoint 'oauth.callback_provider'
    - the rule is owned by the oauth blueprint (no shadowing)
    - the canonical parameterized endpoint 'oauth.callback_provider' is present
    """
    # Fetch rules directly by the endpoint name to handle any Werkzeug converter variation
    rules = _rules_for(app, "oauth.callback_provider")
    assert rules, "No rule registered for endpoint 'oauth.callback_provider'"

    endpoints = _endpoints_of(rules)
    assert (
        "oauth.callback_provider" in endpoints
    ), f"Expected 'oauth.callback_provider' in endpoints; found: {sorted(endpoints)}"

    # Ensure ownership is exclusive to oauth and not shadowed by other blueprints
    _assert_owned_by_oauth(rules)


def test_no_shadowed_or_duplicate_callback_routes(app):
    """
    Extra guard: for each of these canonical rules/endpoints ensure:
    - rules exist
    - all endpoints for that rule are owned by oauth
    - there are not endpoints from multiple different blueprints for the same rule
    """
    targets = [
        "/callback/google",
        "/callback/microsoft",
        "oauth.callback_provider",
    ]
    for path in targets:
        rules = _rules_for(app, path)
        assert rules, f"No rule registered for target: {path}"

        endpoints = _endpoints_of(rules)
        # Sanity: no duplicate blueprints owning the same rule
        blueprints = {e.split(".", 1)[0] for e in endpoints}
        assert (
            len(blueprints) == 1 and "oauth" in blueprints
        ), f"Expected only 'oauth' to own rule {path}; found blueprints: {sorted(blueprints)} with endpoints: {sorted(endpoints)}"

        # Also assert endpoints are unique (no duplicate identical endpoints)
        assert (
            len(endpoints) == len(set(endpoints))
        ), f"Duplicate endpoints detected for target {path}: {sorted(endpoints)}"
