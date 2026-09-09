from pathlib import Path
from uuid import UUID

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.serialization import Encoding, NoEncryption, PrivateFormat


KEYS_DIRECTORY = Path(__file__).resolve().parent.parent / "keys"


def private_key_path(organization_id: UUID) -> Path:
    return KEYS_DIRECTORY / f"organization_{organization_id}_private.pem"


def save_private_key(organization_id: UUID, private_key: Ed25519PrivateKey) -> Path:
    KEYS_DIRECTORY.mkdir(parents=True, exist_ok=True)
    path = private_key_path(organization_id)
    path.write_bytes(private_key.private_bytes(Encoding.PEM, PrivateFormat.PKCS8, NoEncryption()))
    try:
        path.chmod(0o600)
    except OSError:
        pass
    return path


def load_private_key(organization_id: UUID) -> Ed25519PrivateKey | None:
    path = private_key_path(organization_id)
    if not path.is_file():
        return None
    from cryptography.hazmat.primitives.serialization import load_pem_private_key

    key = load_pem_private_key(path.read_bytes(), password=None)
    if not isinstance(key, Ed25519PrivateKey):
        raise TypeError("Organization private key is not Ed25519")
    return key
