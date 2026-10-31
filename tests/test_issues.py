import pytest
from fastapi.testclient import TestClient

import routers.issues
from tests.helpers import add_member, create_project, sign_up_and_log_in


def test_team_opens_discusses_and_closes_an_issue(client: TestClient, monkeypatch: pytest.MonkeyPatch):
    owner = sign_up_and_log_in(client, "owner@example.com")
    project_id = create_project(client, owner)["id"]
    author = add_member(client, owner, project_id, "author@example.com")
    teammate = add_member(client, owner, project_id, "teammate@example.com")
    outsider = sign_up_and_log_in(client, "outsider@example.com")

    labels = {label["name"]: label["id"] for label in client.get(f"/api/projects/{project_id}/labels", headers=owner).json()}
    other_project_id = create_project(client, outsider, name="Other")["id"]
    foreign_label_id = client.get(f"/api/projects/{other_project_id}/labels", headers=outsider).json()[0]["id"]

    foreign_label = client.post(
        f"/api/projects/{project_id}/issues",
        json={"title": "Login button doesn't work", "label_ids": [foreign_label_id]},
        headers=author,
    )
    assert foreign_label.status_code == 400

    created = client.post(
        f"/api/projects/{project_id}/issues",
        json={"title": "Login button doesn't work", "description": "Nothing happens on click", "label_ids": [labels["bug"]]},
        headers=author,
    )
    assert created.status_code == 201
    issue = created.json()
    issue_url = f"/api/issues/{issue['id']}"
    assert issue["status"] == "OPEN"
    assert issue["closed_at"] is None
    assert issue["author"]["email"] == "author@example.com"
    assert [label["name"] for label in issue["labels"]] == ["bug"]

    assert client.get(issue_url, headers=outsider).status_code == 404
    assert client.get(f"/api/projects/{project_id}/issues", headers=outsider).status_code == 404

    for text, commenter in [("I can reproduce this", teammate), ("Fix incoming", author), ("Thanks!", owner)]:
        assert client.post(f"{issue_url}/comments", json={"text": text}, headers=commenter).status_code == 201
    # Order isn't checked: now() is frozen for the whole test transaction, so created_at ties.
    comments = client.get(f"{issue_url}/comments", headers=teammate).json()
    assert {comment["text"] for comment in comments} == {"I can reproduce this", "Fix incoming", "Thanks!"}
    second_page = client.get(f"{issue_url}/comments", params={"limit": 2, "offset": 1}, headers=teammate).json()
    assert len(second_page) == 2

    # A member who is neither the author nor the owner can read but not edit.
    teammate_close = client.patch(issue_url, json={"status": "CLOSED"}, headers=teammate)
    assert teammate_close.status_code == 403

    closed = client.patch(issue_url, json={"status": "CLOSED", "label_ids": [labels["bug"], labels["feature"]]}, headers=author)
    assert closed.status_code == 200
    assert closed.json()["status"] == "CLOSED"
    assert closed.json()["closed_at"] is not None
    assert len(closed.json()["labels"]) == 2

    issues_url = f"/api/projects/{project_id}/issues"
    assert client.get(issues_url, params={"status": "OPEN"}, headers=teammate).json() == []
    assert len(client.get(issues_url, params={"status": "CLOSED"}, headers=teammate).json()) == 1
    assert len(client.get(issues_url, params={"label_id": labels["feature"]}, headers=teammate).json()) == 1

    client.post(issues_url, json={"title": "Add dark mode", "label_ids": [labels["feature"]]}, headers=teammate)
    summary = client.get(f"/api/projects/{project_id}/summary", headers=teammate).json()
    assert summary["open_issues"] == 1
    assert summary["closed_issues"] == 1
    assert [(label["name"], label["issue_count"]) for label in summary["top_labels"]] == [("feature", 2), ("bug", 1)]

    reopened = client.patch(issue_url, json={"status": "OPEN"}, headers=owner)
    assert reopened.json()["status"] == "OPEN"
    assert reopened.json()["closed_at"] is None

    # Skip the per-word delay so the test doesn't wait on a sleep.
    monkeypatch.setattr(routers.issues, "STREAM_WORD_DELAY_SECONDS", 0)
    with client.stream("GET", f"{issue_url}/summary/stream", headers=teammate) as stream:
        chunks = list(stream.iter_text())
    assert len(chunks) > 1
    assert "".join(chunks).startswith('This issue, "Login button doesn\'t work", is still open.')

def test_only_the_owner_manages_labels(client: TestClient):
    owner = sign_up_and_log_in(client, "owner@example.com")
    project_id = create_project(client, owner)["id"]
    member = add_member(client, owner, project_id, "member@example.com")
    labels_url = f"/api/projects/{project_id}/labels"

    assert client.post(labels_url, json={"name": "urgent"}, headers=member).status_code == 403
    assert client.post(labels_url, json={"name": "bug"}, headers=owner).status_code == 409

    created = client.post(labels_url, json={"name": "urgent"}, headers=owner)
    assert created.status_code == 201
    label_url = f"/api/labels/{created.json()['id']}"

    issue = client.post(
        f"/api/projects/{project_id}/issues",
        json={"title": "Checkout is down", "label_ids": [created.json()["id"]]},
        headers=member,
    ).json()

    assert client.patch(label_url, json={"name": "p0"}, headers=member).status_code == 403
    renamed = client.patch(label_url, json={"name": "p0"}, headers=owner)
    assert renamed.json()["name"] == "p0"
    assert client.patch(label_url, json={"name": "feature"}, headers=owner).status_code == 409

    assert client.delete(label_url, headers=member).status_code == 403
    assert client.delete(label_url, headers=owner).status_code == 204
    assert [label["name"] for label in client.get(labels_url, headers=member).json()] == ["bug", "feature"]
    # Deleting a label also removes it from every issue it tagged.
    assert client.get(f"/api/issues/{issue['id']}", headers=member).json()["labels"] == []
