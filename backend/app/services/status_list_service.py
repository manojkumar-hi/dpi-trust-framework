import base64
import gzip
import jwt
from datetime import datetime, timezone
from uuid import UUID
from typing import Tuple

from sqlalchemy import select
from sqlalchemy.orm import Session
from sqlalchemy.orm import selectinload
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

from app.models.bitstring_status_list import BitstringStatusList
from app.models.organization_identity import OrganizationIdentity
from app.services.organization_key_service import load_private_key

MAX_INDEX = 131072
BITSTRING_LENGTH = 16384  # bytes


class StatusListError(Exception):
    pass


def _set_bit(bitstring: bytearray, index: int, val: bool) -> None:
    if index < 0 or index >= MAX_INDEX:
        raise ValueError("Index out of bounds")
    byte_idx = index // 8
    bit_idx = index % 8
    if val:
        bitstring[byte_idx] |= (1 << (7 - bit_idx))
    else:
        bitstring[byte_idx] &= ~(1 << (7 - bit_idx))


def _get_bit(bitstring: bytes, index: int) -> bool:
    if index < 0 or index >= MAX_INDEX:
        raise ValueError("Index out of bounds")
    byte_idx = index // 8
    bit_idx = index % 8
    return bool(bitstring[byte_idx] & (1 << (7 - bit_idx)))


def _encode_bitstring(bitstring: bytes) -> str:
    compressed = gzip.compress(bitstring)
    b64url = base64.urlsafe_b64encode(compressed).decode('ascii').rstrip('=')
    return f"u{b64url}"


def _decode_bitstring(encoded: str) -> bytes:
    if not encoded.startswith('u'):
        raise ValueError("Expected multibase base64url encoded string starting with 'u'")
    b64url = encoded[1:]
    padding = '=' * (4 - (len(b64url) % 4)) if len(b64url) % 4 != 0 else ''
    try:
        compressed = base64.urlsafe_b64decode(b64url + padding)
    except Exception as e:
        raise ValueError("Invalid base64 encoding") from e

    import zlib
    decomp = zlib.decompressobj(wbits=31)
    try:
        bitstring = decomp.decompress(compressed, max_length=BITSTRING_LENGTH + 1)
        if decomp.unconsumed_tail:
            raise ValueError("Compressed data decodes to more than allowed length")
    except zlib.error as e:
        raise ValueError("Invalid compressed bitstring") from e

    if len(bitstring) != BITSTRING_LENGTH:
        raise ValueError("Invalid bitstring length after decompression")
    return bitstring


def get_active_status_list(db: Session, issuer_did: str) -> BitstringStatusList:
    # Use FOR UPDATE to lock the row and prevent concurrent allocations to the same index
    stmt = select(BitstringStatusList).where(
        BitstringStatusList.issuer_did == issuer_did,
        BitstringStatusList.status_purpose == "revocation",
        BitstringStatusList.current_index < MAX_INDEX
    ).with_for_update().order_by(BitstringStatusList.created_at.desc())
    
    status_list = db.scalar(stmt)
    if status_list is None:
        status_list = BitstringStatusList(
            issuer_did=issuer_did,
            status_purpose="revocation",
            bitstring=bytes(BITSTRING_LENGTH),
            current_index=0
        )
        db.add(status_list)
        db.flush()
    return status_list


def allocate_index(db: Session, issuer_did: str) -> Tuple[UUID, int]:
    """Allocates a new index on the active status list for the issuer."""
    status_list = get_active_status_list(db, issuer_did)
    idx = status_list.current_index
    status_list.current_index += 1
    # DB flush will be handled by the caller transaction
    return status_list.id, idx


def set_status(db: Session, list_id: UUID, index: int, revoked: bool) -> None:
    """Updates the status bit for a given index."""
    stmt = select(BitstringStatusList).where(BitstringStatusList.id == list_id).with_for_update()
    status_list = db.scalar(stmt)
    if not status_list:
        raise StatusListError("Status list not found")
    
    bitstring_array = bytearray(status_list.bitstring)
    _set_bit(bitstring_array, index, revoked)
    status_list.bitstring = bytes(bitstring_array)
    status_list.updated_at = datetime.now(timezone.utc)
    db.flush()


def build_and_sign_status_list_vc(db: Session, list_id: UUID, base_url: str) -> str:
    """Generates the signed JWT for the status list and stores it."""
    stmt = select(BitstringStatusList).where(BitstringStatusList.id == list_id).with_for_update()
    status_list = db.scalar(stmt)
    if not status_list:
        raise StatusListError("Status list not found")
        
    issuer_identity = db.scalar(
        select(OrganizationIdentity)
        .options(selectinload(OrganizationIdentity.keys))
        .where(OrganizationIdentity.did == status_list.issuer_did)
    )
    if not issuer_identity:
        raise StatusListError("Issuer identity not found")
        
    active_key = next((k for k in issuer_identity.keys if k.status == "active"), None)
    if not active_key:
        raise StatusListError("No active signing key found for issuer")
    kid = active_key.verification_method
    
    private_key = load_private_key(issuer_identity.organization_id)
    if not private_key:
        raise StatusListError("Private key unavailable")

    now = datetime.now(timezone.utc)
    # The ID of the status list credential
    list_url = f"{base_url}/.well-known/status-lists/{list_id}"
    
    vc_payload = {
        "iss": issuer_identity.did,
        "sub": list_url,
        "jti": list_url,
        "iat": int(now.timestamp()),
        "vc": {
            "@context": [
                "https://www.w3.org/2018/credentials/v1",
                "https://w3id.org/vc/bitstring-status-list/v1"
            ],
            "type": ["VerifiableCredential", "BitstringStatusListCredential"],
            "credentialSubject": {
                "id": f"{list_url}#list",
                "type": "BitstringStatusList",
                "statusPurpose": status_list.status_purpose,
                "encodedList": _encode_bitstring(status_list.bitstring)
            }
        }
    }

    vc_jwt = jwt.encode(
        vc_payload, 
        private_key, 
        algorithm="EdDSA", 
        headers={"kid": kid}
    )
    
    status_list.status_list_vc_jwt = vc_jwt
    db.flush()
    return vc_jwt


def verify_and_check_status(db: Session, vc_jwt: str, index: int) -> bool:
    """
    Verifies a Status List VC JWT and checks the revocation status at the given index.
    Returns True if revoked, False if valid.
    Raises StatusListError if verification fails (FAIL CLOSED).
    """
    try:
        unverified_header = jwt.get_unverified_header(vc_jwt)
        kid = unverified_header.get("kid")
        if not kid:
            raise StatusListError("Missing kid in Status List JWT")
            
        unverified_payload = jwt.decode(vc_jwt, options={"verify_signature": False})
        issuer_did = unverified_payload.get("iss")
        if not issuer_did:
            raise StatusListError("Missing issuer in Status List JWT")
            
        from app.core.config import get_settings
        settings = get_settings()
        
        is_local_issuer = False
        if settings.did_web_domain and issuer_did.startswith(f"did:web:{settings.did_web_domain}"):
            is_local_issuer = True
        elif not settings.did_web_domain:
            is_local_issuer = True
            
        public_key_bytes = None
        
        if is_local_issuer:
            issuer_identity = db.scalar(
                select(OrganizationIdentity)
                .options(selectinload(OrganizationIdentity.keys))
                .where(OrganizationIdentity.did == issuer_did)
            )
            if not issuer_identity:
                if settings.did_web_domain:
                    raise StatusListError("Local Status List issuer not found in registry")
                else:
                    is_local_issuer = False
                    
        if is_local_issuer and issuer_identity:
            signing_key_record = next((k for k in issuer_identity.keys if k.verification_method == kid), None)
            if not signing_key_record:
                raise StatusListError("Status List signing key not found")
                
            issued_at_ts = unverified_payload.get("iat")
            if issued_at_ts is None:
                raise StatusListError("Missing iat in Status List JWT")
            
            issued_at = datetime.fromtimestamp(issued_at_ts, tz=timezone.utc)
            
            valid_from = signing_key_record.valid_from
            if valid_from.tzinfo is None:
                valid_from = valid_from.replace(tzinfo=timezone.utc)
                
            valid_until = signing_key_record.valid_until
            if valid_until and valid_until.tzinfo is None:
                valid_until = valid_until.replace(tzinfo=timezone.utc)
            
            if valid_from > issued_at:
                raise StatusListError("Signing key was not valid at issuance time")
            if valid_until and valid_until < issued_at:
                raise StatusListError("Signing key was expired at issuance time")
                
            public_key_bytes = base64.b64decode(signing_key_record.public_key)
            
        else:
            # Foreign Status List Issuer Resolution
            from app.services.did_web_resolution_service import resolve_did_web, DIDResolutionError
            try:
                did_doc = resolve_did_web(issuer_did)
            except DIDResolutionError as e:
                raise StatusListError(f"Failed to resolve foreign status list DID '{issuer_did}': {e}")
                
            verification_methods = did_doc.get("verificationMethod", [])
            signing_key_vm = next((vm for vm in verification_methods if vm.get("id") == kid), None)
            
            if signing_key_vm is None:
                raise StatusListError(f"Key '{kid}' is not known in foreign DID document '{issuer_did}'")
                
            public_key_bytes = base64.b64decode(signing_key_vm.get("publicKeyBase64"))
            
            issued_at_ts = unverified_payload.get("iat")
            if issued_at_ts is None:
                raise StatusListError("Missing iat in Status List JWT")
            issued_at = datetime.fromtimestamp(issued_at_ts, tz=timezone.utc)

        
        # Verify VC JWT
        public_key = Ed25519PublicKey.from_public_bytes(public_key_bytes)
        payload = jwt.decode(
            vc_jwt,
            public_key,
            algorithms=["EdDSA"],
            issuer=issuer_did,
            options={
                "verify_exp": True,
                "verify_nbf": True,
                "verify_iat": True,
            }
        )
        
        vc_claim = payload.get("vc", {})
        if "BitstringStatusListCredential" not in vc_claim.get("type", []):
            raise StatusListError("Invalid credential type for Status List")
            
        credential_subject = vc_claim.get("credentialSubject", {})
        if credential_subject.get("statusPurpose") != "revocation":
            raise StatusListError("Invalid statusPurpose (only revocation supported)")
            
        encoded_list = credential_subject.get("encodedList")
        if not encoded_list:
            raise StatusListError("Missing encodedList")
            
        bitstring = _decode_bitstring(encoded_list)
        return _get_bit(bitstring, index)
        
    except Exception as e:
        if isinstance(e, StatusListError):
            raise
        raise StatusListError(f"Status list verification failed: {e}") from e


from cachetools import TTLCache
from app.utils.http_client import fetch_status_list_artifact, HTTPClientError

_STATUS_LIST_CACHE = TTLCache(maxsize=1000, ttl=300)

def resolve_and_verify_status_list(db: Session, status_list_url: str, index: int) -> bool:
    """
    Fetches the status list from the URL (or cache) and cryptographically verifies it.
    Returns True if revoked, False if active.
    Raises StatusListError on any failure.
    """
    vc_jwt = _STATUS_LIST_CACHE.get(status_list_url)
    if not vc_jwt:
        try:
            raw_bytes = fetch_status_list_artifact(status_list_url)
            vc_jwt = raw_bytes.decode('utf-8')
        except HTTPClientError as e:
            raise StatusListError(f"Failed to fetch status list: {e}")
        except UnicodeDecodeError:
            raise StatusListError("Status list artifact is not valid UTF-8 text")
            
        _STATUS_LIST_CACHE[status_list_url] = vc_jwt
        
    return verify_and_check_status(db, vc_jwt, index)
