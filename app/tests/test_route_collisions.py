# /home/srpihhllc/PlaidBridgeOpenBankingApi/app/tests/test_route_collisions.py


def test_no_route_collisions(app):
    """
    Detects duplicate route rules + HTTP methods.
    Ensures no blueprint accidentally overrides another.
    """

    rules = {}
    collisions = []

    for rule in app.url_map.iter_rules():
        key = (rule.rule, tuple(sorted(rule.methods - {"HEAD", "OPTIONS"})))

        if key in rules:
            collisions.append(
                {
                    "rule": rule.rule,
                    "methods": list(rule.methods),
                    "existing_endpoint": rules[key],
                    "new_endpoint": rule.endpoint,
                }
            )
        else:
            rules[key] = rule.endpoint

    if collisions:
        msg_lines = ["ROUTE COLLISION DETECTED:\n"]
        for c in collisions:
            msg_lines.append(
                f"- Path: {c['rule']}  Methods: {c['methods']}\n"
                f"  Existing endpoint: {c['existing_endpoint']}\n"
                f"  New endpoint:      {c['new_endpoint']}\n"
            )
        raise AssertionError("\n".join(msg_lines))
