import time
import pytest
import jwt
from cryptography.hazmat.primitives.asymmetric import rsa, ec
from cryptography.hazmat.primitives import serialization
from unittest.mock import MagicMock, patch
import httpx
from datetime import datetime, timedelta, timezone

from app.core.auth import (
    JWTValidator, AuthError, TOKEN_MISSING, TOKEN_MALFORMED,
    TOKEN_SIGNATURE_INVALID, TOKEN_EXPIRED, TOKEN_NOT_YET_VALID,
    INVALID_ISSUER, INVALID_AUDIENCE, UNSUPPORTED_ALGORITHM,
    MISSING_SUBJECT, MISSING_KID, UNKNOWN_KID, JWKS_UNAVAILABLE
)

# Test-only cryptographic keys
# Generate RSA Key
rsa_private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
rsa_public_key = rsa_private_key.public_key()
rsa_pem = rsa_public_key.public_bytes(
    encoding=serialization.Encoding.PEM,
    format=serialization.PublicFormat.SubjectPublicKeyInfo
).decode()

# Generate EC Key
ec_private_key = ec.generate_private_key(ec.SECP256R1())
ec_public_key = ec_private_key.public_key()

# Generate another RSA Key for "invalid signature" checks
bad_rsa_private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)


@pytest.fixture
def validator(monkeypatch):
    from app.core.config import get_settings
    settings = get_settings()
    monkeypatch.setattr(settings, "auth_jwt_issuer", "https://auth.test")
    monkeypatch.setattr(settings, "auth_jwt_audience", "test-audience")
    monkeypatch.setattr(settings, "auth_static_public_key", None)
    monkeypatch.setattr(settings, "auth_jwks_url", "https://auth.test/.well-known/jwks.json")
    monkeypatch.setattr(settings, "auth_clock_skew_seconds", 5)
    
    # Return a fresh instance so caches are empty
    return JWTValidator()

def mint_token(private_key, kid="test-kid", alg="RS256", iss="https://auth.test", aud="test-audience", sub="user-123", exp_delta_sec=3600, nbf_delta_sec=0, extra_headers=None):
    now = datetime.now(timezone.utc)
    payload = {
        "iss": iss,
        "aud": aud,
        "sub": sub,
        "iat": now,
        "exp": now + timedelta(seconds=exp_delta_sec),
        "nbf": now + timedelta(seconds=nbf_delta_sec)
    }
    # Remove claims if set to None
    payload = {k: v for k, v in payload.items() if v is not None}
    
    headers = {"kid": kid}
    if extra_headers:
        headers.update(extra_headers)
        
    return jwt.encode(payload, private_key, algorithm=alg, headers=headers)


def mock_jwks_response(kid="test-kid", kty="RSA", public_key_obj=rsa_public_key, alg="RS256"):
    import json
    # Generate JWK dict
    if kty == "RSA":
        jwk_dict = json.loads(jwt.algorithms.RSAAlgorithm.to_jwk(public_key_obj))
    else:
        jwk_dict = json.loads(jwt.algorithms.ECAlgorithm.to_jwk(public_key_obj))
        
    jwk_dict["kid"] = kid
    jwk_dict["alg"] = alg
    
    response = MagicMock(spec=httpx.Response)
    response.json.return_value = {"keys": [jwk_dict]}
    response.raise_for_status = MagicMock()
    return response


def test_valid_rs256_token(validator, monkeypatch):
    token = mint_token(rsa_private_key, alg="RS256")
    
    # Mock JWKS fetch
    mock_get = MagicMock(return_value=mock_jwks_response(kty="RSA", public_key_obj=rsa_public_key))
    monkeypatch.setattr(validator._http_client, "get", mock_get)
    
    claims = validator.validate_token(token)
    assert claims["sub"] == "user-123"
    assert mock_get.call_count == 1
    
    # Calling again should use cache
    validator.validate_token(token)
    assert mock_get.call_count == 1


def test_valid_es256_token(validator, monkeypatch):
    token = mint_token(ec_private_key, kid="ec-kid", alg="ES256")
    
    mock_get = MagicMock(return_value=mock_jwks_response(kid="ec-kid", kty="EC", public_key_obj=ec_public_key, alg="ES256"))
    monkeypatch.setattr(validator._http_client, "get", mock_get)
    
    claims = validator.validate_token(token)
    assert claims["sub"] == "user-123"


def test_invalid_signature(validator, monkeypatch):
    # Signed with wrong key
    token = mint_token(bad_rsa_private_key)
    
    mock_get = MagicMock(return_value=mock_jwks_response(public_key_obj=rsa_public_key))
    monkeypatch.setattr(validator._http_client, "get", mock_get)
    
    with pytest.raises(AuthError) as exc:
        validator.validate_token(token)
    assert exc.value.code == TOKEN_SIGNATURE_INVALID


def test_alg_none(validator, monkeypatch):
    import base64
    # Force alg=none by removing signature
    header = base64.urlsafe_b64encode(b'{"alg":"none","kid":"test-kid"}').decode('ascii').rstrip("=")
    payload = base64.urlsafe_b64encode(b'{"iss":"https://auth.test","aud":"test-audience","sub":"123"}').decode('ascii').rstrip("=")
    token = f"{header}.{payload}."
    
    with pytest.raises(AuthError) as exc:
        validator.validate_token(token)
    assert exc.value.code == UNSUPPORTED_ALGORITHM


def test_unsupported_algorithm(validator, monkeypatch):
    # We only support RS256/ES256, if HS256 is used:
    token = jwt.encode({"sub": "123"}, "secret", algorithm="HS256", headers={"kid": "test-kid"})
    with pytest.raises(AuthError) as exc:
        validator.validate_token(token)
    assert exc.value.code == UNSUPPORTED_ALGORITHM


def test_expired_token(validator, monkeypatch):
    token = mint_token(rsa_private_key, exp_delta_sec=-100) # expired 100 seconds ago
    mock_get = MagicMock(return_value=mock_jwks_response())
    monkeypatch.setattr(validator._http_client, "get", mock_get)
    
    with pytest.raises(AuthError) as exc:
        validator.validate_token(token)
    assert exc.value.code == TOKEN_EXPIRED


def test_not_yet_valid_token(validator, monkeypatch):
    token = mint_token(rsa_private_key, nbf_delta_sec=100) # valid 100 seconds from now
    mock_get = MagicMock(return_value=mock_jwks_response())
    monkeypatch.setattr(validator._http_client, "get", mock_get)
    
    with pytest.raises(AuthError) as exc:
        validator.validate_token(token)
    assert exc.value.code == TOKEN_NOT_YET_VALID


def test_bounded_clock_skew(validator, monkeypatch):
    # Skew is 5 seconds.
    # Expiry 3 seconds ago should still be valid.
    token = mint_token(rsa_private_key, exp_delta_sec=-3)
    mock_get = MagicMock(return_value=mock_jwks_response())
    monkeypatch.setattr(validator._http_client, "get", mock_get)
    
    claims = validator.validate_token(token) # Should pass
    assert claims["sub"] == "user-123"


def test_invalid_issuer(validator, monkeypatch):
    token = mint_token(rsa_private_key, iss="https://wrong.issuer")
    mock_get = MagicMock(return_value=mock_jwks_response())
    monkeypatch.setattr(validator._http_client, "get", mock_get)
    
    with pytest.raises(AuthError) as exc:
        validator.validate_token(token)
    assert exc.value.code == INVALID_ISSUER


def test_invalid_audience(validator, monkeypatch):
    token = mint_token(rsa_private_key, aud="wrong-audience")
    mock_get = MagicMock(return_value=mock_jwks_response())
    monkeypatch.setattr(validator._http_client, "get", mock_get)
    
    with pytest.raises(AuthError) as exc:
        validator.validate_token(token)
    assert exc.value.code == INVALID_AUDIENCE


def test_missing_sub(validator, monkeypatch):
    token = mint_token(rsa_private_key, sub=None)
    mock_get = MagicMock(return_value=mock_jwks_response())
    monkeypatch.setattr(validator._http_client, "get", mock_get)
    
    with pytest.raises(AuthError) as exc:
        validator.validate_token(token)
    assert exc.value.code == MISSING_SUBJECT


def test_missing_kid(validator, monkeypatch):
    token = jwt.encode({"sub": "123", "iss": "https://auth.test", "aud": "test-audience"}, rsa_private_key, algorithm="RS256")
    # kid is omitted
    with pytest.raises(AuthError) as exc:
        validator.validate_token(token)
    assert exc.value.code == MISSING_KID


def test_unknown_kid(validator, monkeypatch):
    token = mint_token(rsa_private_key, kid="unknown-kid")
    mock_get = MagicMock(return_value=mock_jwks_response(kid="test-kid")) # Returns different kid
    monkeypatch.setattr(validator._http_client, "get", mock_get)
    
    with pytest.raises(AuthError) as exc:
        validator.validate_token(token)
    assert exc.value.code == UNKNOWN_KID


def test_malformed_token(validator):
    with pytest.raises(AuthError) as exc:
        validator.validate_token("not.a.token")
    assert exc.value.code == TOKEN_MALFORMED


def test_jwks_unavailable(validator, monkeypatch):
    token = mint_token(rsa_private_key)
    mock_get = MagicMock(side_effect=httpx.HTTPError("Connection failed"))
    monkeypatch.setattr(validator._http_client, "get", mock_get)
    
    with pytest.raises(AuthError) as exc:
        validator.validate_token(token)
    assert exc.value.code == JWKS_UNAVAILABLE


def test_jwks_unknown_kid_refresh_throttling(validator, monkeypatch):
    token1 = mint_token(rsa_private_key, kid="kid1")
    token2 = mint_token(rsa_private_key, kid="kid2")
    
    mock_get = MagicMock(return_value=mock_jwks_response(kid="kid1"))
    monkeypatch.setattr(validator._http_client, "get", mock_get)
    
    validator.validate_token(token1)
    assert mock_get.call_count == 1
    
    # Now kid2 comes in, it's unknown. But we just refreshed (throttled).
    with pytest.raises(AuthError) as exc:
        validator.validate_token(token2)
    assert exc.value.code == UNKNOWN_KID
    assert mock_get.call_count == 1  # Throttled, no second call
    
    # Fast forward time
    validator._last_jwks_refresh = time.time() - 20.0
    mock_get.return_value = mock_jwks_response(kid="kid2")
    validator.validate_token(token2)
    assert mock_get.call_count == 2
