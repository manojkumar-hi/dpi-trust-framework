import pytest
from unittest.mock import AsyncMock, MagicMock

import app.models  # Ensure all models are registered with Base metadata

@pytest.fixture(autouse=True)
def mock_fabric_ledger_client(monkeypatch):
    mock_client = AsyncMock()
    mock_client.issue_delegation.return_value = {"success": True, "transaction_id": "test_txn_123"}
    mock_client.verify_delegation.return_value = {"success": True, "result": {"valid": True}}
    mock_client.revoke_delegation.return_value = {"success": True, "transaction_id": "test_txn_456"}
    
    mock_class = MagicMock(return_value=mock_client)
    monkeypatch.setattr("app.services.delegation_service.FabricLedgerClient", mock_class)
    return mock_client

@pytest.fixture(autouse=True)
def mock_status_list_fetch(monkeypatch):
    """Globally mock status list fetches to hit the test client, avoiding DNS errors in tests."""
    from fastapi.testclient import TestClient
    from app.main import app
    import app.services.status_list_service as sl_service
    
    sync_client = TestClient(app)
    
    def mock_fetch(url: str):
        list_id = url.split("/")[-1]
        # Ignore query params or fragments if any
        list_id = list_id.split("#")[0]
        list_id = list_id.split("?")[0]
        
        res = sync_client.get(f"/.well-known/status-lists/{list_id}")
        if res.status_code == 200:
            return res.content
        raise Exception(f"Not found: {url}")
        
    monkeypatch.setattr(sl_service, "fetch_status_list_artifact", mock_fetch)
