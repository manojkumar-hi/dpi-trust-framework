import json
import logging
import urllib.parse
from cachetools import TTLCache
from app.utils.http_client import fetch_json_artifact, HTTPClientError

logger = logging.getLogger(__name__)

class DIDResolutionError(Exception):
    pass

_DID_DOCUMENT_CACHE = TTLCache(maxsize=1000, ttl=300)

def _build_did_web_url(did: str) -> str:
    if not did.startswith("did:web:"):
        raise DIDResolutionError(f"Unsupported DID method: {did}")
        
    identifier = did[8:]
    parts = identifier.split(":")
    
    if len(parts) == 1:
        # e.g. did:web:example.com
        domain = urllib.parse.unquote(parts[0])
        return f"https://{domain}/.well-known/did.json"
    else:
        # e.g. did:web:example.com:agents:123
        domain = urllib.parse.unquote(parts[0])
        path = "/".join(urllib.parse.unquote(p) for p in parts[1:])
        return f"https://{domain}/{path}/did.json"

def _validate_did_document(did: str, did_doc: dict):
    if not isinstance(did_doc, dict):
        raise DIDResolutionError("DID Document must be a JSON object")
        
    doc_id = did_doc.get("id")
    if doc_id != did:
        raise DIDResolutionError(f"DID Document ID mismatch: expected {did}, got {doc_id}")
        
    verification_methods = did_doc.get("verificationMethod", [])
    if not isinstance(verification_methods, list) or not verification_methods:
        raise DIDResolutionError("DID Document must contain 'verificationMethod' list")
        
    for vm in verification_methods:
        if not isinstance(vm, dict):
            raise DIDResolutionError("Verification method must be an object")
            
        vm_id = vm.get("id")
        if not vm_id or not isinstance(vm_id, str):
            raise DIDResolutionError("Verification method must have an 'id'")
            
        vm_type = vm.get("type")
        if vm_type != "Ed25519VerificationKey2020":
            raise DIDResolutionError(f"Unsupported verification method type: {vm_type}")
            
        controller = vm.get("controller")
        if controller != doc_id:
            raise DIDResolutionError(f"Verification method controller mismatch: expected {doc_id}, got {controller}")
            
        if "publicKeyBase64" not in vm or not isinstance(vm.get("publicKeyBase64"), str):
            raise DIDResolutionError("Verification method must contain 'publicKeyBase64'")

def resolve_did_web(did: str) -> dict:
    """
    Resolves a did:web DID over HTTPS and returns the validated DID Document.
    Uses in-memory cache to prevent redundant fetches.
    """
    cached_doc = _DID_DOCUMENT_CACHE.get(did)
    if cached_doc:
        return cached_doc
        
    url = _build_did_web_url(did)
    
    try:
        raw_bytes = fetch_json_artifact(url)
    except HTTPClientError as e:
        raise DIDResolutionError(f"Failed to fetch DID Document: {e}")
        
    try:
        did_doc = json.loads(raw_bytes.decode('utf-8'))
    except (UnicodeDecodeError, json.JSONDecodeError) as e:
        raise DIDResolutionError(f"Invalid JSON in DID Document: {e}")
        
    _validate_did_document(did, did_doc)
    
    _DID_DOCUMENT_CACHE[did] = did_doc
    return did_doc
