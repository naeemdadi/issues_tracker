from fastapi.testclient import TestClient

DEFAULT_PASSWORD = "correct-horse-battery"

AuthHeaders = dict[str, str]

def sign_up_and_log_in(client: TestClient, email: str) -> AuthHeaders:
    signup = client.post("/api/signup", json={"email": email, "password": DEFAULT_PASSWORD})
    assert signup.status_code == 201, signup.text

    login = client.post("/api/login", json={"email": email, "password": DEFAULT_PASSWORD})
    assert login.status_code == 200, login.text
    return {"Authorization": f"Bearer {login.json()['access_token']}"}

def create_project(client: TestClient, owner: AuthHeaders, name: str = "Website") -> dict:
    response = client.post("/api/projects", json={"name": name}, headers=owner)
    assert response.status_code == 201, response.text
    return response.json()

def add_member(client: TestClient, owner: AuthHeaders, project_id: str, email: str) -> AuthHeaders:
    member = sign_up_and_log_in(client, email)

    invite = client.post(f"/api/projects/{project_id}/members", json={"email": email}, headers=owner)
    assert invite.status_code == 201, invite.text

    accept = client.post(f"/api/projects/{project_id}/members/accept", headers=member)
    assert accept.status_code == 200, accept.text
    return member
