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
