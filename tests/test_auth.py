from fastapi.testclient import TestClient

from tests.helpers import DEFAULT_PASSWORD


def test_user_can_sign_up_log_in_and_reach_protected_routes(client: TestClient):
    too_short = client.post("/api/signup", json={"email": "ada@example.com", "password": "short"})
    assert too_short.status_code == 422

    signup = client.post("/api/signup", json={"email": "Ada@Example.com", "password": DEFAULT_PASSWORD})
    assert signup.status_code == 201
    user = signup.json()
    assert user["email"] == "ada@example.com"
    assert "password" not in user
    assert "password_hash" not in user

    duplicate = client.post("/api/signup", json={"email": "ADA@example.com", "password": DEFAULT_PASSWORD})
    assert duplicate.status_code == 409

    wrong_password = client.post("/api/login", json={"email": "ada@example.com", "password": "not-the-password"})
    unknown_email = client.post("/api/login", json={"email": "nobody@example.com", "password": DEFAULT_PASSWORD})
    assert wrong_password.status_code == 401
    # Same error either way, so the API doesn't reveal which emails are registered.
    assert wrong_password.json() == unknown_email.json()

    login = client.post("/api/login", json={"email": "ADA@example.com", "password": DEFAULT_PASSWORD})
    assert login.status_code == 200
    token = login.json()["access_token"]

    assert client.get("/api/projects").status_code == 401
    assert client.get("/api/projects", headers={"Authorization": "Bearer not-a-real-token"}).status_code == 401

    projects = client.get("/api/projects", headers={"Authorization": f"Bearer {token}"})
    assert projects.status_code == 200
    assert projects.json() == []
