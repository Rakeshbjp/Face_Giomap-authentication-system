"""
Encryption utilities for securing face embeddings at rest.
Uses Fernet symmetric encryption (AES-128-CBC) from the cryptography library.
"""

import base64
import json
import logging
from typing import List

from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

from app.config.settings import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


def _get_fernet_key() -> bytes:
    """
    Derive a Fernet-compatible encryption key from the configured secret.
    Uses PBKDF2 key derivation for added security.
    """
    key_material = settings.EMBEDDING_ENCRYPTION_KEY.encode("utf-8")
    salt = b"face_auth_salt_v1"  # Static salt — in production, per-user salt is better

    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=salt,
        iterations=100_000,
    )
    derived_key = kdf.derive(key_material)
    return base64.urlsafe_b64encode(derived_key)


def encrypt_embeddings(embeddings: List[List[float]]) -> List[str]:
    """
    Encrypt a list of face embedding vectors.

    Args:
        embeddings: List of embedding vectors (each vector is a list of floats).

    Returns:
        List of encrypted, base64-encoded embedding strings.
    """
    try:
        fernet = Fernet(_get_fernet_key())
        encrypted = []

        for embedding in embeddings:
            # Serialize embedding to JSON string, then encrypt
            embedding_json = json.dumps(embedding)
            encrypted_bytes = fernet.encrypt(embedding_json.encode("utf-8"))
            encrypted.append(encrypted_bytes.decode("utf-8"))

        logger.debug(f"Encrypted {len(encrypted)} embeddings")
        return encrypted

    except Exception as e:
        logger.error(f"Embedding encryption failed: {e}")
        raise RuntimeError(f"Failed to encrypt embeddings: {e}")


def decrypt_embeddings(encrypted_embeddings: List[str]) -> List[List[float]]:
    """
    Decrypt a list of encrypted face embedding strings.

    Args:
        encrypted_embeddings: List of encrypted embedding strings from the database.

    Returns:
        List of decrypted embedding vectors.
    """
    try:
        fernet = Fernet(_get_fernet_key())
        decrypted = []

        for enc_str in encrypted_embeddings:
            decrypted_bytes = fernet.decrypt(enc_str.encode("utf-8"))
            embedding = json.loads(decrypted_bytes.decode("utf-8"))
            decrypted.append(embedding)

        logger.debug(f"Decrypted {len(decrypted)} embeddings")
        return decrypted

    except Exception as e:
        logger.error(f"Embedding decryption failed: {e}")
        raise RuntimeError(f"Failed to decrypt embeddings: {e}")
