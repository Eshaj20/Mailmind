import os
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

os.environ["DATABASE_URL"] = "sqlite+pysqlite:///:memory:"
os.environ["SECRET_KEY"] = "test-secret-key-at-least-16"
os.environ["GOOGLE_CLIENT_ID"] = "test-google-client"
os.environ["GOOGLE_CLIENT_SECRET"] = "test-google-secret"
os.environ["SYNC_JOB_MAX_ATTEMPTS"] = "3"

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.api.deps import get_db  # noqa: E402
from app.db.base import Base  # noqa: E402
from app.main import create_app  # noqa: E402


@pytest.fixture()
def db_session() -> Session:
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    TestingSessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    Base.metadata.create_all(bind=engine)
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


@pytest.fixture()
def client(db_session: Session) -> TestClient:
    def override_get_db():
        yield db_session

    app = create_app()
    app.dependency_overrides[get_db] = override_get_db
    return TestClient(app)
