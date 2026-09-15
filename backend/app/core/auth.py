import logging
import time
from typing import Any, Dict, Optional

import httpx
import jwt
from cachetools import TTLCache
from cryptography.hazmat.primitives import serialization

from app.core.config import get_settings

logger = logging.getLogger(__name__)


class AuthError(Exception):
    def __init__(self, code: str, detail: str = ""):
        self.code = code
        self.detail = detail
        super().__init__(f"{code}: {detail}")


# Safe reason codes for audit
TOKEN_MISSING = "TOKEN_MISSING"
TOKEN_MALFORMED = "TOKEN_MALFORMED"
TOKEN_SIGNATURE_INVALID = "TOKEN_SIGNATURE_INVALID"
TOKEN_EXPIRED = "TOKEN_EXPIRED"
TOKEN_NOT_YET_VALID = "TOKEN_NOT_YET_VALID"
INVALID_ISSUER = "INVALID_ISSUER"
INVALID_AUDIENCE = "INVALID_AUDIENCE"
UNSUPPORTED_ALGORITHM = "UNSUPPORTED_ALGORITHM"
IDENTITY_NOT_FOUND = "IDENTITY_NOT_FOUND"
IDENTITY_REVOKED = "IDENTITY_REVOKED"
IDENTITY_MISMATCH = "IDENTITY_MISMATCH"
IDENTITY_AMBIGUOUS = "IDENTITY_AMBIGUOUS"
MISSING_SUBJECT = "MISSING_SUBJECT"
MISSING_KID = "MISSING_KID"
UNKNOWN_KID = "UNKNOWN_KID"
JWKS_UNAVAILABLE = "JWKS_UNAVAILABLE"


class JWTValidator:
    def __init__(self):
        self.settings = get_settings()
        # Bounded in-memory TTLCache for JWKS keys (key_id -> PyJWT RSAAlgorithm/ECAlgorithm object)
        # Store max 100 keys, TTL of 60 minutes
        self._jwks_cache = TTLCache(maxsize=100, ttl=3600)
        self._last_jwks_refresh = 0.0
        self._refresh_cooldown = 10.0  # Prevent refresh abuse (max 1 request per 10 seconds)
        self._http_client = httpx.Client(timeout=5.0)

    def _fetch_jwks(self) -> None:
        """Fetches JWKS from the configured URL and updates the cache."""
        now = time.time()
        if now - self._last_jwks_refresh < self._refresh_cooldown:
            return  # Throttled

        jwks_url = self.settings.auth_jwks_url
        if not jwks_url:
            return

        self._last_jwks_refresh = now
        try:
            response = self._http_client.get(jwks_url)
            response.raise_for_status()
            jwks_data = response.json()
            keys = jwks_data.get("keys", [])
            for key_data in keys:
                kid = key_data.get("kid")
                if kid:
                    alg = key_data.get("alg")
                    if alg and alg.startswith("ES"):
                        public_key = jwt.algorithms.ECAlgorithm.from_jwk(key_data)
                    else:
                        public_key = jwt.algorithms.RSAAlgorithm.from_jwk(key_data)
                    self._jwks_cache[kid] = public_key
        except Exception as e:
            logger.error(f"Failed to fetch JWKS: {e}")
            raise AuthError(JWKS_UNAVAILABLE, "Could not fetch JWKS")

    def _get_public_key(self, kid: Optional[str]) -> Any:
        """Retrieves the public key for a given kid, refreshing JWKS if necessary."""
        # 1. Dev/Test static key support
        if self.settings.auth_static_public_key:
            return serialization.load_pem_public_key(self.settings.auth_static_public_key.encode())

        # 2. Production JWKS support
        if not self.settings.auth_jwks_url:
            raise AuthError(JWKS_UNAVAILABLE, "No static key or JWKS URL configured")

        if not kid:
            raise AuthError(MISSING_KID, "kid header is required when using JWKS")

        if kid not in self._jwks_cache:
            self._fetch_jwks()

        if kid not in self._jwks_cache:
            raise AuthError(UNKNOWN_KID, f"Key ID {kid} not found in JWKS")

        return self._jwks_cache[kid]

    def validate_token(self, token: str) -> Dict[str, Any]:
        """
        Validates the JWT and returns the claims.
        """
        if not token:
            raise AuthError(TOKEN_MISSING, "Token is missing")

        try:
            unverified_headers = jwt.get_unverified_header(token)
        except jwt.DecodeError:
            raise AuthError(TOKEN_MALFORMED, "Token is malformed")

        alg = unverified_headers.get("alg")
        if alg not in ["RS256", "ES256"]:
            raise AuthError(UNSUPPORTED_ALGORITHM, f"Algorithm {alg} is not supported")

        kid = unverified_headers.get("kid")

        try:
            public_key = self._get_public_key(kid)
        except AuthError as e:
            raise e

        try:
            payload = jwt.decode(
                token,
                public_key,
                algorithms=["RS256", "ES256"],
                issuer=self.settings.auth_jwt_issuer,
                audience=self.settings.auth_jwt_audience,
                leeway=self.settings.auth_clock_skew_seconds,
            )
        except jwt.ExpiredSignatureError:
            raise AuthError(TOKEN_EXPIRED, "Token has expired")
        except jwt.ImmatureSignatureError:
            raise AuthError(TOKEN_NOT_YET_VALID, "Token is not yet valid")
        except jwt.InvalidIssuerError:
            raise AuthError(INVALID_ISSUER, "Invalid issuer")
        except jwt.InvalidAudienceError:
            raise AuthError(INVALID_AUDIENCE, "Invalid audience")
        except jwt.InvalidSignatureError:
            raise AuthError(TOKEN_SIGNATURE_INVALID, "Invalid signature")
        except jwt.PyJWTError as e:
            raise AuthError(TOKEN_MALFORMED, str(e))

        sub = payload.get("sub")
        if not sub:
            raise AuthError(MISSING_SUBJECT, "Token must contain a 'sub' claim")

        return payload

class JWTIssuer:
    def __init__(self):
        self.settings = get_settings()

    def issue_token(self, subject: str, org_id: str, agent_id: str | None = None, expires_in_seconds: int = 3600) -> str:
        if not self.settings.auth_static_private_key:
            raise RuntimeError("auth_static_private_key is not configured")

        private_key = serialization.load_pem_private_key(
            self.settings.auth_static_private_key.encode(),
            password=None
        )

        now = int(time.time())
        payload = {
            "iss": self.settings.auth_jwt_issuer,
            "aud": self.settings.auth_jwt_audience,
            "sub": subject,
            "dpi_org_id": org_id,
            "iat": now,
            "exp": now + expires_in_seconds
        }
        if agent_id:
            payload["dpi_agent_id"] = agent_id

        return jwt.encode(payload, private_key, algorithm="RS256")

validator = JWTValidator()
issuer = JWTIssuer()
