# =============================================================================
# FILE: /home/srpihhllc/PlaidBridgeOpenBankingApi/app/tests/test_route_collisions.py
# DESCRIPTION: Detect duplicate route rules and method collisions across blueprints.
# =============================================================================

def test_no_route_collisions(app):
    """
    Detects duplicate route rules + HTTP methods.
    Ensures no blueprint accidentally overrides another while ignoring
    intentional endpoint aliases (e.g., admin_ui.* mirroring admin.*).
    """

    rules = {}
    collisions = []

    for rule in app.url_map.iter_rules():
        key = (rule.rule, tuple(sorted(rule.methods - {"HEAD", "OPTIONS"})))

        if key in rules:
            existing_ep = rules[key]
            new_ep = rule.endpoint

            # Allow intentional backward-compatibility aliases (e.g., admin_ui.* aliasing admin.*)
            is_admin_alias = (
                (existing_ep.startswith("admin.") and new_ep.startswith("admin_ui."))
                or (existing_ep.startswith("admin_ui.") and new_ep.startswith("admin."))
            ) and existing_ep.split(".", 1)[1] == new_ep.split(".", 1)[1]

            # 🚨 DEFENSIVE CHECK: It is only a genuine collision if a
            # DIFFERENT non-alias endpoint string tries to hijack the same path/method combination.
            if existing_ep != new_ep and not is_admin_alias:
                collisions.append(
                    {
                        "rule": rule.rule,
                        "methods": list(rule.methods),
                        "existing_endpoint": existing_ep,
                        "new_endpoint": new_ep,
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