def test_debug_urlmap(app):
    """Print the URL map so we can see what endpoints survived pruning."""
    rules = sorted(
        [
            (r.rule, r.endpoint, sorted(r.methods - {"HEAD", "OPTIONS"}))
            for r in app.url_map.iter_rules()
        ]
    )

    print("\n=== URL MAP ===")
    for rule, endpoint, methods in rules:
        print(f"{rule:30}  ->  {endpoint:40}  {methods}")

    # Assert the Google callback endpoints exist
    assert any(
        r.endpoint == "oauth.callback_google" for r in app.url_map.iter_rules()
    ), "callback_google missing"

    assert any(
        r.endpoint == "oauth.callback_google_clean"
        for r in app.url_map.iter_rules()
    ), "callback_google_clean missing"
