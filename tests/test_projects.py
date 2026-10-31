from fastapi.testclient import TestClient

from tests.helpers import create_project, sign_up_and_log_in


def test_owner_builds_a_team_by_inviting_and_removing_members(client: TestClient):
    owner = sign_up_and_log_in(client, "owner@example.com")
    teammate = sign_up_and_log_in(client, "teammate@example.com")
    outsider = sign_up_and_log_in(client, "outsider@example.com")

    project = create_project(client, owner, name="Website")
    project_id = project["id"]
    assert project["role"] == "OWNER"
    assert project["status"] == "ACCEPTED"

    starter_labels = client.get(f"/api/projects/{project_id}/labels", headers=owner).json()
    assert [label["name"] for label in starter_labels] == ["bug", "feature"]

    renamed = client.patch(f"/api/projects/{project_id}", json={"name": "Marketing site"}, headers=owner)
    assert renamed.json()["name"] == "Marketing site"

    # Non-members get 404, not 403, so they can't tell the project exists.
    assert client.get(f"/api/projects/{project_id}", headers=outsider).status_code == 404

    unknown = client.post(f"/api/projects/{project_id}/members", json={"email": "ghost@example.com"}, headers=owner)
    assert unknown.status_code == 404

    invite = client.post(f"/api/projects/{project_id}/members", json={"email": "teammate@example.com"}, headers=owner)
    assert invite.status_code == 201
    assert invite.json()["status"] == "INVITED"
    repeat_invite = client.post(f"/api/projects/{project_id}/members", json={"email": "teammate@example.com"}, headers=owner)
    assert repeat_invite.status_code == 409

    # An invite shows up in the teammate's list but doesn't grant access yet.
    [pending] = client.get("/api/projects", headers=teammate).json()
    assert pending["status"] == "INVITED"
    assert client.get(f"/api/projects/{project_id}", headers=teammate).status_code == 404

    accepted = client.post(f"/api/projects/{project_id}/members/accept", headers=teammate)
    assert accepted.status_code == 200
    assert accepted.json()["role"] == "MEMBER"
    assert client.get(f"/api/projects/{project_id}", headers=teammate).status_code == 200

    members = client.get(f"/api/projects/{project_id}/members", headers=teammate).json()
    assert {member["user"]["email"] for member in members} == {"owner@example.com", "teammate@example.com"}

    member_rename = client.patch(f"/api/projects/{project_id}", json={"name": "Hijacked"}, headers=teammate)
    member_invite = client.post(f"/api/projects/{project_id}/members", json={"email": "outsider@example.com"}, headers=teammate)
    assert member_rename.status_code == 403
    assert member_invite.status_code == 403

    owner_id = next(member["user"]["id"] for member in members if member["role"] == "OWNER")
    teammate_id = next(member["user"]["id"] for member in members if member["role"] == "MEMBER")
    assert client.delete(f"/api/projects/{project_id}/members/{owner_id}", headers=owner).status_code == 400

    assert client.delete(f"/api/projects/{project_id}/members/{teammate_id}", headers=owner).status_code == 204
    assert client.get(f"/api/projects/{project_id}", headers=teammate).status_code == 404
    assert client.get("/api/projects", headers=teammate).json() == []
