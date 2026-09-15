from uuid import UUID
from datetime import datetime, timezone, timedelta
from app.models.challenge import Challenge
from app.services.vp_auth_service import create_challenge
import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.database.connection import get_db
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from app.database.base import Base

engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base.metadata.create_all(bind=engine)

@pytest.fixture
def override_get_db():
    def _override():
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = _override
    yield _override
    app.dependency_overrides.pop(get_db, None)

@pytest.fixture
def client():
    return TestClient(app)

def test_challenge_creation(override_get_db):
    db = next(override_get_db())
    challenge = create_challenge(db)

    assert isinstance(challenge.id, UUID)
    assert len(challenge.nonce) >= 32
    assert challenge.audience == "did:web:trust.dpi.local"
    assert challenge.consumed_at is None
    assert challenge.expires_at > challenge.issued_at

def test_api_challenge_generation(client, override_get_db):
    response = client.post("/auth/challenges")
    assert response.status_code == 200
    data = response.json()
    assert "challenge_id" in data
    assert "nonce" in data
    assert "audience" in data
    assert "expires_at" in data
    assert data["audience"] == "did:web:trust.dpi.local"
