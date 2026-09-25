import sys
import os
import requests
import time
from datetime import datetime, timedelta, timezone
from sqlalchemy import create_engine, text
from pprint import pprint
import subprocess
import json

engine = create_engine('postgresql+psycopg://dpi_user:dpi_password@localhost:5432/dpi_trust_db')

def get_counts():
    with engine.connect() as conn:
        tables = ['organizations', 'agents', 'organization_identities', 'organization_identity_keys', 'agent_identities', 'delegations', 'verifiable_credentials']
        return {t: conn.execute(text(f'SELECT COUNT(*) FROM {t}')).scalar() for t in tables}

print("=== BASELINE COUNTS ===")
counts = get_counts()
pprint(counts)

BASE_URL = "http://localhost:8000"

with engine.connect() as conn:
    org_id = conn.execute(text("SELECT id FROM organizations LIMIT 1")).scalar()
    agent_id = conn.execute(text("SELECT id FROM agents LIMIT 1")).scalar()
    other_org_id = conn.execute(text(f"SELECT id FROM organizations WHERE id != '{org_id}' LIMIT 1")).scalar()

print(f"\nUsing Org ID: {org_id}")
print(f"Using Agent ID: {agent_id}")

print("\n=== STEP 4: REAL END-TO-END DELEGATION ===")
now = datetime.now(timezone.utc)
payload = {
    "delegator_organization_id": str(org_id),
    "delegatee_agent_id": str(agent_id),
    "purpose": "Phase 6 E2E Test",
    "starts_at": now.isoformat(),
    "expires_at": (now + timedelta(days=365)).isoformat(),
    "capabilities": [{"capability_code": "agent.read"}]
}

headers = {"X-Mock-Principal-Org-Id": str(org_id)}

resp = requests.post(f"{BASE_URL}/delegations", json=payload, headers=headers)
print("Create Delegation status:", resp.status_code)
if resp.status_code != 201:
    print(resp.text)
    sys.exit(1)
    
del_data = resp.json()
delegation_id = del_data["id"]
print("Created Delegation ID:", delegation_id)
print("Fabric Tx ID:", del_data.get("fabric_transaction_id"))

print("\n=== STEP 5: UNIFIED VERIFICATION ===")
v_resp = requests.get(f"{BASE_URL}/delegations/{delegation_id}/verify", headers=headers)
print("Verify status:", v_resp.status_code)
v_data = v_resp.json()
print(f"valid: {v_data['valid']}, signature_valid: {v_data['signature_valid']}, hash_valid: {v_data['hash_valid']}")

print("\n=== STEP 6: AUTHORIZATION TESTS ===")
# 2. Different organization principal attempts to issue
bad_headers = {"X-Mock-Principal-Org-Id": str(other_org_id)}
resp2 = requests.post(f"{BASE_URL}/delegations", json=payload, headers=bad_headers)
print(f"Different org issue -> {resp2.status_code}")

# 4. Different organization principal attempts to revoke
revoke_payload = {"reason": "Test Phase 6"}
resp3 = requests.post(f"{BASE_URL}/delegations/{delegation_id}/revoke", json=revoke_payload, headers=bad_headers)
print(f"Different org revoke -> {resp3.status_code}")

print("\n=== STEP 7: REVOCATION ===")
resp4 = requests.post(f"{BASE_URL}/delegations/{delegation_id}/revoke", json=revoke_payload, headers=headers)
print(f"Authorized org revoke -> {resp4.status_code}")
revoke_data = resp4.json()
print("Revoke Fabric Tx ID:", revoke_data.get("fabric_transaction_id", "N/A"))

print("\n=== STEP 8: IDEMPOTENT REVOCATION ===")
resp5 = requests.post(f"{BASE_URL}/delegations/{delegation_id}/revoke", json=revoke_payload, headers=headers)
print(f"Repeat revoke -> {resp5.status_code}")

print("\n=== FINAL COUNTS ===")
pprint(get_counts())
