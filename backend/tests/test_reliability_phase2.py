import pytest
from uuid import uuid4
from fastapi.testclient import TestClient
from app.main import app
from app.database.connection import SessionLocal
from app.models.audit_record import AuditRecord
from app.core.auth import JWTValidator
from unittest.mock import patch

client = TestClient(app)

def test_unauthenticated_agent_creation():
    from app.api.dependencies import get_current_principal
    # Ensure no mock override is active — other test modules may install one at import time
    saved_override = app.dependency_overrides.pop(get_current_principal, None)
    try:
        org_id = uuid4()
        response = client.post("/agents", json={"organization_id": str(org_id), "name": "Test Agent", "agent_type": "standard"})
        assert response.status_code == 401
        
        db = SessionLocal()
        records = db.query(AuditRecord).filter_by(event_type="authentication_failed", reason_code="TOKEN_MISSING").all()
        assert len(records) >= 1
        db.close()
    finally:
        if saved_override is not None:
            app.dependency_overrides[get_current_principal] = saved_override

def test_authenticated_but_unauthorized_agent_creation():
    org_id_1 = uuid4()  # the org the principal belongs to
    org_id_2 = uuid4()  # a different org
    
    from app.api.dependencies import get_current_principal, Principal
    
    # Store old override if it exists
    old_override = app.dependency_overrides.get(get_current_principal)
    
    app.dependency_overrides[get_current_principal] = lambda: Principal(organization_id=org_id_1)
    
    try:
        response = client.post("/agents", json={"organization_id": str(org_id_2), "name": "Test Agent", "agent_type": "standard"})
        assert response.status_code == 403
    finally:
        if old_override:
            app.dependency_overrides[get_current_principal] = old_override
        else:
            app.dependency_overrides.pop(get_current_principal, None)

