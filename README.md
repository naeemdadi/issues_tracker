# FastAPI Issue Tracker

A small GitHub Issues style API. Teams create projects, invite teammates, open issues, tag them with labels and discuss them in comments.

Built with FastAPI, SQLAlchemy 2, Alembic and PostgreSQL.

## Features

- Sign up and log in with email and password (JWT bearer tokens)
- Create projects and invite teammates by email
- Open issues, tag them with labels and close them when they're fixed
- Comment on issues
- Project summary with open/closed counts and the most used labels
- A word-by-word streamed issue summary (placeholder text for now, a real AI summary later)

## Access rules

- Only accepted project members can see a project's issues.
- Only the issue author or the project owner can edit or close an issue.
- Only the project owner can manage members and labels.

## Requirements

- [uv](https://docs.astral.sh/uv/) for Python and dependencies
- Docker for the local Postgres database

## Getting started

Install dependencies:

```bash
uv sync
```

Start Postgres:

```bash
docker compose up -d
```

Create your `.env` from the example:

```bash
cp .env.example .env
```

Then edit `.env`. To use the database from `compose.yaml` set:

```
DATABASE_URL=postgresql+psycopg://issues_user:issues_password@localhost:5432/issue_tracker
SECRET_KEY=<a long random string>
```

You can generate a secret key with:

```bash
uv run python -c "import secrets; print(secrets.token_urlsafe(32))"
```

Create the tables:

```bash
uv run alembic upgrade head
```

Run the dev server:

```bash
uv run fastapi dev main.py
```

The API runs at http://127.0.0.1:8000. Interactive docs are at http://127.0.0.1:8000/docs.

## Configuration

Settings are read from `.env` (see `config.py`).

| Variable | Required | Default | Purpose |
| --- | --- | --- | --- |
| `DATABASE_URL` | yes | | SQLAlchemy URL for Postgres |
| `SECRET_KEY` | yes | | Signs the JWT access tokens |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | no | `30` | How long a login token lasts |
| `ECHO` | no | `false` | Log every SQL statement |

## Authentication

Call `POST /api/login` with a JSON body of `email` and `password`. Send the returned `access_token` on every other request:

```
Authorization: Bearer <access_token>
```

## API overview

All routes live under `/api`.

| Method | Path | What it does |
| --- | --- | --- |
| POST | `/signup` | Create an account |
| POST | `/login` | Get an access token |
| GET | `/projects` | List your projects |
| POST | `/projects` | Create a project (you become the owner) |
| GET | `/projects/{project_id}` | Get one project |
| PATCH | `/projects/{project_id}` | Rename a project (owner only) |
| GET | `/projects/{project_id}/summary` | Issue counts and top labels |
| GET | `/projects/{project_id}/members` | List members |
| POST | `/projects/{project_id}/members` | Invite a user by email (owner only) |
| POST | `/projects/{project_id}/members/accept` | Accept your pending invite |
| DELETE | `/projects/{project_id}/members/{user_id}` | Remove a member or cancel an invite (owner only) |
| GET | `/projects/{project_id}/labels` | List labels |
| POST | `/projects/{project_id}/labels` | Create a label (owner only) |
| PATCH | `/labels/{label_id}` | Update a label (owner only) |
| DELETE | `/labels/{label_id}` | Delete a label (owner only) |
| GET | `/projects/{project_id}/issues` | List issues, filter with `?status=OPEN` or `?label_id=` |
| POST | `/projects/{project_id}/issues` | Open an issue |
| GET | `/issues/{issue_id}` | Get one issue |
| PATCH | `/issues/{issue_id}` | Edit or close an issue (author or owner) |
| GET | `/issues/{issue_id}/summary/stream` | Stream a summary word by word |
| GET | `/issues/{issue_id}/comments` | List comments |
| POST | `/issues/{issue_id}/comments` | Add a comment |

Invites work in two steps. The owner invites someone who already has an account. That person then calls the accept endpoint before they can see the project.

## Database migrations

Alembic is configured in `pyproject.toml` and reads `DATABASE_URL` from `.env`.

After changing `models.py`, generate and apply a migration:

```bash
uv run alembic revision --autogenerate -m "describe the change"
uv run alembic upgrade head
```

Always read the generated file in `migrations/versions/` before applying it. Autogenerate misses some changes, like renamed columns.

## Running tests

Tests use a separate `issue_tracker_test` database in the same Postgres container. Create it once:

```bash
docker compose exec db createdb -U issues_user issue_tracker_test
```

Then run:

```bash
uv run pytest
```

Each test runs inside a transaction that's rolled back at the end, so tests never see each other's data. To use a different database set `TEST_DATABASE_URL`. Its name must end in `_test` because the suite drops every table.

Useful options:

```bash
uv run pytest -v                                   # one line per test
uv run pytest tests/test_issues.py                 # one file
uv run pytest tests/test_auth.py::test_user_can_sign_up_log_in_and_reach_protected_routes
uv run pytest -x                                   # stop at the first failure
uv run pytest -s                                   # show print() output
```

## Project layout

```
main.py           App setup and router registration
config.py         Settings loaded from .env
database.py       Engine, session factory and the get_db dependency
models.py         SQLAlchemy tables
schemas.py        Pydantic request and response models
security.py       Password hashing and JWT helpers
dependencies.py   Shared dependencies: current user, project access checks, paging
routers/          One module per resource
migrations/       Alembic environment and migration scripts
tests/            pytest suite: fixtures in conftest.py, shared helpers in helpers.py
compose.yaml      Local Postgres
```
