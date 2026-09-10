import hashlib
import json
from datetime import datetime, timezone
from typing import Any, Iterable, Mapping
from uuid import UUID


PROOF_TYPE = "Ed25519Signature2020"


def normalize_utc_timestamp(value: datetime) -> str:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("Delegation timestamps must be timezone-aware")
    normalized = value.astimezone(timezone.utc)
    return normalized.isoformat(timespec="microseconds").replace("+00:00", "Z")


def _canonical_json_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")


def _canonical_capability(capability: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "capabilityCode": capability["capabilityCode"],
        "constraints": capability.get("constraints", {}),
        "scope": capability.get("scope", {}),
    }


def canonical_delegation_document(
    *,
    delegation_id: UUID,
    delegator_did: str,
    delegatee_did: str,
    parent_delegation_id: UUID | None,
    root_delegation_id: UUID,
    depth: int,
    purpose: str,
    starts_at: datetime,
    expires_at: datetime,
    issued_at: datetime,
    capabilities: Iterable[Mapping[str, Any]],
    allow_subdelegation: bool = False,
    max_delegation_depth: int = 0,
) -> dict[str, Any]:
    normalized_capabilities = [_canonical_capability(capability) for capability in capabilities]
    normalized_capabilities.sort(key=_canonical_json_bytes)
    return {
        "capabilities": normalized_capabilities,
        "constraints": {
            "allowSubdelegation": allow_subdelegation,
            "expiresAt": normalize_utc_timestamp(expires_at),
            "maxDelegationDepth": max_delegation_depth,
            "startsAt": normalize_utc_timestamp(starts_at),
        },
        "delegatee": {"did": delegatee_did, "type": "Agent"},
        "delegationId": str(delegation_id),
        "depth": depth,
        "delegator": {"did": delegator_did, "type": "Organization"},
        "issuedAt": normalize_utc_timestamp(issued_at),
        "parentDelegationId": (
            str(parent_delegation_id) if parent_delegation_id is not None else None
        ),
        "purpose": purpose,
        "rootDelegationId": str(root_delegation_id),
        "type": "DPIAuthorityDelegation",
    }


def canonical_delegation_bytes(**kwargs: Any) -> bytes:
    return _canonical_json_bytes(canonical_delegation_document(**kwargs))


def delegation_hash(**kwargs: Any) -> str:
    return hashlib.sha256(canonical_delegation_bytes(**kwargs)).hexdigest()