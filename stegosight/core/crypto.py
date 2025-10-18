"""Cryptography interface definitions."""
from __future__ import annotations

from typing import Protocol


class ICrypto(Protocol):
    """Protocol describing crypto helpers used by the GUI layer."""

    def encrypt_aes_gcm(self, data: bytes, password: str, kdf_params: dict) -> bytes:
        """Encrypt *data* using AES-GCM with key derived from *password*."""

    def decrypt_aes_gcm(self, data: bytes, password: str, kdf_params: dict) -> bytes:
        """Decrypt *data* using AES-GCM with key derived from *password*."""
