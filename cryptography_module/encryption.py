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
    """Encrypt/Decrypt data with AES-256-GCM (AEAD)."""

    def encrypt(self, plaintext: bytes, password: str) -> bytes:
        """Encrypt *plaintext* with *password*.

        The returned blob layout is ``[salt][nonce][ciphertext]`` where the
        salt length is configurable via :mod:`config`.
        """

        try:
            key, salt, meta = derive_key(password)
            nonce = os.urandom(12)  # 96-bit nonce recommended for GCM
            aesgcm = AESGCM(key)
            ct = aesgcm.encrypt(nonce, plaintext, None)
            blob = salt + nonce + ct
            log_operation(
                logger,
                "Encrypt",
                status="SUCCESS",
                details=f"kdf={meta.get('kdf')}",
            )
            return blob
        except Exception as exc:  # pragma: no cover - defensive logging
            log_operation(logger, "Encrypt", status="FAILED", details=str(exc))
            raise

    def decrypt(self, blob: bytes, password: str) -> bytes:
        """Decrypt *blob* that was produced by :meth:`encrypt`."""

        try:
            salt_len = CRYPTO_SETTINGS.get("salt_bytes", 16)
            if len(blob) < salt_len + 12:
                raise ValueError("Ciphertext blob is too short to contain salt and nonce")

            salt = blob[:salt_len]
            nonce = blob[salt_len : salt_len + 12]
            ciphertext = blob[salt_len + 12 :]
            key, _, meta = derive_key(password, salt=salt)
            aesgcm = AESGCM(key)
            plaintext = aesgcm.decrypt(nonce, ciphertext, None)
            log_operation(
                logger,
                "Decrypt",
                status="SUCCESS",
                details=f"kdf={meta.get('kdf')}",
            )
            return plaintext
        except Exception as exc:  # pragma: no cover - defensive logging
            log_operation(logger, "Decrypt", status="FAILED", details=str(exc))
            raise


_MANAGER = CryptoManager()


def _coerce_bytes(data: bytes | bytearray | memoryview) -> bytes:
    """Accept common binary buffer types and return them as ``bytes``."""

    if isinstance(data, bytes):
        return data
    if isinstance(data, bytearray):
        return bytes(data)
    if isinstance(data, memoryview):
        return data.tobytes()
    raise TypeError("Data must be bytes-like")


def encrypt_data(data: bytes | bytearray | memoryview, password: str) -> bytes:
    """Convenience wrapper used throughout the GUI pipeline.

    Parameters
    ----------
    data:
        Raw payload to protect.  The function accepts any bytes-like object to
        simplify integration with PyQt and worker threads.
    password:
        Passphrase provided by the user.
    """

    if not isinstance(password, str) or not password:
        raise ValueError("Password must be a non-empty string")
    return _MANAGER.encrypt(_coerce_bytes(data), password)


def decrypt_data(blob: bytes | bytearray | memoryview, password: str) -> bytes:
    """Reverse :func:`encrypt_data` and return the original plaintext."""

    if not isinstance(password, str) or not password:
        raise ValueError("Password must be a non-empty string")
    return _MANAGER.decrypt(_coerce_bytes(blob), password)


__all__ = ["CryptoManager", "encrypt_data", "decrypt_data"]
