"""Encryption helpers for STEGOSIGHT."""

from __future__ import annotations

import os
from typing import Iterable

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from utils.logger import log_operation, setup_logger

try:  # pragma: no cover - configuration may be absent in tests
    from config import CRYPTO_SETTINGS
except Exception:  # pragma: no cover - fallback for standalone tests
    CRYPTO_SETTINGS = {"salt_bytes": 16}

from .key_derivation import derive_key

logger = setup_logger(__name__)


class CryptoManager:
    """Encrypt/Decrypt data with AES-256-GCM (AEAD)"""

    def __init__(self):
        pass

    def encrypt(self, plaintext: bytes, password: str) -> bytes:
        """Encrypt and return blob: ``[salt][nonce][ciphertext]``."""

        try:
            key, salt, meta = derive_key(password)
            nonce = os.urandom(12)  # 96-bit nonce recommended for GCM
            aesgcm = AESGCM(key)
            ct = aesgcm.encrypt(nonce, plaintext, None)
            blob = salt + nonce + ct
            log_operation(
                logger, "Encrypt", status="SUCCESS", details=f"kdf={meta.get('kdf')}"
            )
            return blob
        except Exception as exc:  # pragma: no cover - defensive logging
            log_operation(logger, "Encrypt", status="FAILED", details=str(exc))
            raise

    def decrypt(self, blob: bytes, password: str) -> bytes:
        """Decrypt a blob produced by :meth:`encrypt`."""

        try:
            salt_len = CRYPTO_SETTINGS.get("salt_bytes", 16)
            salt = blob[:salt_len]
            nonce = blob[salt_len : salt_len + 12]
            ct = blob[salt_len + 12 :]
            key, _, meta = derive_key(password, salt=salt)
            aesgcm = AESGCM(key)
            pt = aesgcm.decrypt(nonce, ct, None)
            log_operation(
                logger, "Decrypt", status="SUCCESS", details=f"kdf={meta.get('kdf')}"
            )
            return pt
        except Exception as e:
            log_operation(logger, "Decrypt", status="FAILED", details=str(e))
            raise


def encrypt_data(plaintext: bytes, password: str) -> bytes:
    """Convenience wrapper that encrypts ``plaintext`` with ``password``."""

    manager = CryptoManager()
    return manager.encrypt(plaintext, password)


def decrypt_data(blob: bytes, password: str) -> bytes:
    """Convenience wrapper mirroring :func:`encrypt_data`."""

    manager = CryptoManager()
    return manager.decrypt(blob, password)
