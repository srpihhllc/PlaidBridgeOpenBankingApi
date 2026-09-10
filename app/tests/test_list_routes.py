# app/tests/test_list_routes.py
def test_list_routes(app):
    """
    Print all registered URL rules so you can see which /dashboard* endpoints exist.
    Run with -s to show the prints in pytest output.
    """
    rules = sorted(app.url_map.iter_rules(), key=lambda r: r.rule)
    print("\n--- Registered routes ---")
    for rule in rules:
        print(rule.rule, sorted(rule.methods), "->", rule.endpoint)
    print("--- End routes ---\n")

    # Sanity assertion so pytest prints the output even if nothing else runs
    assert any(
        r.rule.startswith("/dashboard") for r in rules
    ), "No dashboard rules found"
