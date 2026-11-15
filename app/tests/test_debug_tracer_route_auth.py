
from types import SimpleNamespace



import pytest





@pytest.mark.parametrize(

    "path",

    [

        "/debug/test",

        "/debug/config",

        "/debug/cortex_map",

        "/debug/self_repair",

        "/tracer/template_tracer",

    ],

)

def test_debug_and_tracer_routes_for_authenticated_non_admin(app, monkeypatch, path):

    non_admin = SimpleNamespace(

        is_authenticated=True,

        role="subscriber",

        roles=["subscriber"],

        is_admin=False,

    )

    monkeypatch.setattr("flask_login.utils._get_user", lambda: non_admin)



    response = app.test_client().get(path, follow_redirects=False)

    assert response.status_code == 403, f"{path} returned {response.status_code}"
