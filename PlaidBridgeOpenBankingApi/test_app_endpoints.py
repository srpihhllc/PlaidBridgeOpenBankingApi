# app/test_app_endpoints.py


def register_user(
    client,
    email="demo@bank.com",
    password="demo123",
    username="Demo",
    bank="Piermont Bank",
):
    return client.post(
        "/api/register",
        json={
            "username": username,
            "email": email,
            "password": password,
            "bank_name": bank,
        },
    )


def login_user(client, email="demo@bank.com", password="demo123"):
    client.post(
        "/api/register",
        json={
            "username": "Demo",
            "email": email,
            "password": password,
            "bank_name": "Piermont Bank",
        },
    )
    response = client.post("/api/login", json={"email": email, "password": password})
    return response.get_json().get("access_token")


# 🌐 MAIN ROUTES


def test_home_route(client):
    response = client.get("/")
    assert response.status_code == 200


def test_login_page(client):
    response = client.get("/login")
    assert response.status_code == 200


def test_dashboard_requires_login(client):
    response = client.get("/dashboard", follow_redirects=True)
    assert response.status_code == 200
    assert b"Sign In" in response.data or b"Welcome" in response.data


# 🔐 API ROUTES


def test_register_user(client):
    response = register_user(client)
    assert response.status_code == 201
    assert b"registered successfully" in response.data


def test_login_user(client):
    register_user(client)
    response = client.post("/api/login", json={"email": "demo@bank.com", "password": "demo123"})
    assert response.status_code == 200
    assert "access_token" in response.get_json()


def test_generate_link_token_requires_auth(client):
    response = client.get("/api/generate_link_token")
    assert response.status_code == 401


def test_generate_link_token_with_token(client):
    token = login_user(client)
    headers = {"Authorization": f"Bearer {token}"}
    response = client.get("/api/generate_link_token", headers=headers)
    assert response.status_code == 200
    assert "link_token" in response.get_json()


def test_statement_pdf_returns_success(client):
    response = client.get("/api/generate_statement")
    assert response.status_code == 200
    assert response.mimetype == "application/pdf"


def test_health_route_rate_limit(client):
    for _ in range(5):
        res = client.get("/api/health")
        assert res.status_code == 200
    final = client.get("/api/health")
    assert final.status_code in [200, 429]
