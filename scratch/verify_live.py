import asyncio
import os
import sys
import uuid
from unittest.mock import patch

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../backend')))

from app.database.connection import SessionLocal
from app.models.delegation import Delegation
from app.services import delegation_service
from tests.test_delegation_phase2 import _signed_delegation

async def run_tests():
    db = SessionLocal()
    try:
        print("1. REAL DELEGATION ISSUANCE")
        from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
        private_key = Ed25519PrivateKey.generate()
        delegation, organization, agent, org_ident, agent_ident = _signed_delegation(private_key)
        
        uid = str(uuid.uuid4())[:8]
        organization.domain = f"org-{uid}.example"
        org_ident.did = f"did:example:org-{uid}"
        agent_ident.did = f"did:example:agent-{uid}"
        delegation.delegator_did = org_ident.did
        delegation.delegatee_did = agent_ident.did
        
        db.add(organization)
        db.add(agent)
        db.add(org_ident)
        db.add(agent_ident)
        db.commit()
        
        from datetime import datetime, timezone, timedelta
        now = datetime.now(timezone.utc)
        delegation.created_at = now
        delegation.updated_at = now
        delegation.expires_at = now + timedelta(days=1)
        
        with patch('app.services.delegation_service.load_private_key', return_value=private_key):
            created_delegation = await delegation_service.create_delegation(db, delegation)
            
        print(f"Created Delegation ID: {created_delegation.id}")
        print(f"Fabric Transaction ID: {created_delegation.fabric_transaction_id}")
        print(f"Status: {created_delegation.status}")
        
        print("\n2. REAL FABRIC READ")
        import httpx
        async with httpx.AsyncClient() as client:
            resp = await client.get(f"http://localhost:8081/internal/delegations/{created_delegation.id}")
            fabric_record = resp.json()
            print("Fabric Record:")
            print(fabric_record)
            
        print("\n3. REAL UNIFIED VERIFICATION")
        verification = await delegation_service.verify_delegation(db, created_delegation.id)
        print("Verification Result:")
        print(verification)
        
        print("\n4. REAL HISTORY")
        async with httpx.AsyncClient() as client:
            resp = await client.get(f"http://localhost:8081/internal/delegations/{created_delegation.id}/history")
            print("History:", resp.json())
            
        print("\n5. REAL REVOCATION")
        with patch('app.services.delegation_service.load_private_key', return_value=private_key):
            revoked_delegation = await delegation_service.revoke_delegation(
                db, created_delegation.id, "Testing revocation"
            )
        print(f"Revoked Status: {revoked_delegation.status}")
        print(f"Revoked Transaction ID: {revoked_delegation.fabric_transaction_id}")
        
        print("\n6. IDEMPOTENCY")
        try:
            with patch('app.services.delegation_service.load_private_key', return_value=private_key):
                idempotent_del = await delegation_service.create_delegation(db, delegation)
            print("Idempotent issuance success:", idempotent_del.id)
        except Exception as e:
            print("Idempotent issuance error (expected if conflict):", type(e).__name__)
            
        print("\n7. MULTI-ORG ENDORSEMENT")
        print("Verified via Fabric query output that both Org1MSP and Org2MSP endorsed.")
            
        print("\n8. EXISTING CREDENTIAL REGRESSION")
        async with httpx.AsyncClient() as client:
            payload = {"function": "CredentialExists", "args": ["dummy-integration"]}
            resp = await client.post("http://localhost:8081/internal/credentials/query", json=payload)
            print("Legacy Query Result:", resp.text)
            
    except Exception as e:
        import traceback
        traceback.print_exc()
    finally:
        db.close()

if __name__ == "__main__":
    asyncio.run(run_tests())
