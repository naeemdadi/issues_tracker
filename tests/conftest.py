import os
from collections.abc import Iterator

# Must run before any app import: config.py reads settings at import time,
# and real env vars beat values from .env.
os.environ["DATABASE_URL"] = os.environ.get(
    "TEST_DATABASE_URL",
    "postgresql+psycopg://issues_user:issues_password@localhost:5432/issue_tracker_test",
)
os.environ["SECRET_KEY"] = "test-secret-key-that-is-at-least-32-bytes"
os.environ["ECHO"] = "false"

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine, create_engine, make_url
from sqlalchemy.orm import Session

from config import settings
from database import get_db
from main import app
from models import Base


@pytest.fixture(scope="session")
def engine() -> Iterator[Engine]:
    # drop_all wipes every table, so refuse to run against anything but a test database.
    database_name = make_url(settings.database_url).database or ""
    if not database_name.endswith("_test"):
        raise RuntimeError(f"Refusing to run tests against non-test database {database_name!r}")

    engine = create_engine(settings.database_url)
    # Dropping first clears tables left behind by a run that crashed.
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    yield engine
    Base.metadata.drop_all(engine)
    engine.dispose()

@pytest.fixture
def db_session(engine: Engine) -> Iterator[Session]:
    connection = engine.connect()
    transaction = connection.begin()
    # The app's commit() only creates a savepoint, so rolling back the outer
    # transaction afterwards leaves the database empty for the next test.
    session = Session(bind=connection, join_transaction_mode="create_savepoint")
    try:
        yield session
    finally:
        session.close()
        transaction.rollback()
        connection.close()

@pytest.fixture
def client(db_session: Session) -> Iterator[TestClient]:
    app.dependency_overrides[get_db] = lambda: db_session
    try:
        with TestClient(app) as test_client:
            yield test_client
    finally:
        app.dependency_overrides.clear()
