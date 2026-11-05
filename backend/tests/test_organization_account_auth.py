from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.dependencies import get_db
from app.database.base import Base
from app.main import app
from app.models.organization import Organization
from app.models.organization_administrator import OrganizationAdministrator
from app.models.revoked_auth_token import RevokedAuthToken


engine = create_engine(
    "sqlite:///:memory:",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


@pytest.fixture
def client(monkeypatch):
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    monkeypatch.setattr("app.services.account_service.save_private_key", lambda *_: None)
    monkeypatch.setattr("app.api.dependencies._audit_auth", lambda *_args, **_kwargs: None)

    def override_get_db():
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    yield TestClient(app)
    app.dependency_overrides.pop(get_db, None)


def registration_payload(email: str):
    return {
        "full_name": "Ada Administrator",
        "email": email,
        "phone": "5550101234",
        "organization_name": "Example Organization",
        "password": "correct horse battery staple",
    }


def test_register_login_logout_and_data_persists(client):
    email = f"admin-{uuid4()}@example.com"
    response = client.post("/auth/register", json=registration_payload(email))
    assert response.status_code == 201
    registration = response.json()
    assert "password" not in response.text

    login = client.post("/auth/login", json={"email": email, "password": "correct horse battery staple"})
    assert login.status_code == 200
    assert login.json()["onboarding_completed"] is False
    token = login.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    current = client.get("/auth/me", headers=headers)
    assert current.status_code == 200
    assert current.json()["email"] == email
    assert current.json()["organization_id"] == registration["organization_id"]
    assert current.json()["onboarding_completed"] is False

    complete = client.post("/auth/onboarding/complete", headers=headers)
    assert complete.status_code == 200
    assert complete.json()["onboarding_completed"] is True

    repeated = client.post("/auth/onboarding/complete", headers=headers)
    assert repeated.status_code == 200
    assert repeated.json()["onboarding_completed"] is True

    logout = client.post("/auth/logout", headers=headers)
    assert logout.status_code == 204
    assert client.get("/auth/me", headers=headers).status_code == 401

    db = TestingSessionLocal()
    try:
        assert db.get(Organization, UUID(registration["organization_id"])) is not None
        assert db.query(OrganizationAdministrator).filter_by(email=email).one().password_hash != "correct horse battery staple"
        assert db.query(RevokedAuthToken).count() == 1
    finally:
        db.close()


def test_duplicate_registration_is_rejected(client):
    email = f"duplicate-{uuid4()}@example.com"
    assert client.post("/auth/register", json=registration_payload(email)).status_code == 201
    duplicate = client.post("/auth/register", json=registration_payload(email.upper()))
    assert duplicate.status_code == 409
    assert "already exists" in duplicate.json()["detail"]


def test_invalid_credentials_are_rejected(client):
    email = f"invalid-{uuid4()}@example.com"
    assert client.post("/auth/register", json=registration_payload(email)).status_code == 201
    response = client.post("/auth/login", json={"email": email, "password": "wrong password"})
    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid email or password"


def test_registration_enforces_phone_and_password_rules(client):
    invalid_phone = registration_payload(f"phone-{uuid4()}@example.com")
    invalid_phone["phone"] = "12345"
    response = client.post("/auth/register", json=invalid_phone)
    assert response.status_code == 422
    assert response.json()["detail"][0]["loc"] == ["body", "phone"]
    assert response.json()["detail"][0]["type"] == "string_too_short"

    invalid_password = registration_payload(f"password-{uuid4()}@example.com")
    invalid_password["password"] = "short"
    response = client.post("/auth/register", json=invalid_password)
    assert response.status_code == 422
    assert response.json()["detail"][0]["loc"] == ["body", "password"]
    assert response.json()["detail"][0]["type"] == "string_too_short"
