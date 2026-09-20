from __future__ import annotations

import os

os.environ.setdefault("DATABASE_URL", "sqlite:///./test-veritydocs.db")
os.environ.setdefault("STORAGE_ROOT", "./test-storage")
os.environ.setdefault("EXTRACTION_PROVIDER", "demo")

import pytest
from fastapi.testclient import TestClient
from veritydocs_api.database import Base, SessionLocal, engine, init_db
from veritydocs_api.main import app


@pytest.fixture(autouse=True)
def reset_database() -> None:
    Base.metadata.drop_all(engine)
    init_db()
    yield
    Base.metadata.drop_all(engine)


@pytest.fixture
def db():
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def client():
    with TestClient(app) as test_client:
        yield test_client
