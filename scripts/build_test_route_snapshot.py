# scripts/build_test_route_snapshot.py

import json
from pathlib import Path

from app.tests.conftest import app as app_fixture

fixture_func = getattr(app_fixture, "__wrapped__", app_fixture)

gen = fixture_func()
application = next(gen)

routes = sorted(
    (
        {
            "rule": rule.rule,
            "methods": sorted(
                m for m in rule.methods
                if m not in {"HEAD", "OPTIONS"}
            ),
            "endpoint": rule.endpoint,
        }
        for rule in application.url_map.iter_rules()
    ),
    key=lambda d: (
        d["rule"],
        d["endpoint"],
        d["methods"],
    ),
)

Path("app/tests/route_snapshot.json").write_text(
    json.dumps(routes, indent=2)
)

print("Routes:", len(routes))

try:
    next(gen)
except StopIteration:
    pass