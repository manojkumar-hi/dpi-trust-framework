import jwt
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from datetime import datetime, timezone

priv = Ed25519PrivateKey.generate()
pub = priv.public_key()

payload = {
    "iss": "did:web:test",
    "sub": "did:web:test:subject",
    "iat": int(datetime.now(timezone.utc).timestamp()),
}

try:
    token = jwt.encode(payload, priv, algorithm="EdDSA", headers={"kid": "key1"})
    print("Token:", token)
except Exception as e:
    print("Encode error:", e)

try:
    decoded = jwt.decode(token, pub, algorithms=["EdDSA"], issuer="did:web:test", subject="did:web:test:subject")
    print("Decoded:", decoded)
except Exception as e:
    import traceback
    traceback.print_exc()
    print("Decode error:", e)
