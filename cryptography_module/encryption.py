"""Encryption Module (AES-256-GCM + Argon2id KDF)
ปลอดภัยตามมาตรฐาน AEAD; รองรับ PBKDF2 fallback หากไม่มี argon2-cffi
"""
import os
from typing import Tuple, Dict, Any
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from utils.logger import setup_logger, log_operation
try:
    from config import CRYPTO_SETTINGS
except Exception:
    CRYPTO_SETTINGS = {"salt_bytes": 16}

from .key_derivation import derive_key

logger = setup_logger(__name__)


class CryptoManager:
    """Encrypt/Decrypt data with AES-256-GCM (AEAD)"""
    def __init__(self):
        pass

    def encrypt(self, plaintext: bytes, password: str) -> bytes:
        """Encrypt and return blob: [salt][nonce][ciphertext]"""
        try:
            key, salt, meta = derive_key(password)
            nonce = os.urandom(12)  # 96-bit nonce
            aesgcm = AESGCM(key)
            ct = aesgcm.encrypt(nonce, plaintext, None)
            blob = salt + nonce + ct
            log_operation(logger, "Encrypt", status="SUCCESS", details=f"kdf={meta.get('kdf')}")
            return blob
        except Exception as e:
            log_operation(logger, "Encrypt", status="FAILED", details=str(e))
            raise

    def decrypt(self, blob: bytes, password: str) -> bytes:
        """Input blob: [salt(16)][nonce(12)][ciphertext...]"""
        try:
            salt_len = CRYPTO_SETTINGS.get('salt_bytes', 16)
            salt = blob[:salt_len]
            nonce = blob[salt_len:salt_len+12]
            ct = blob[salt_len+12:]
            key, _, meta = derive_key(password, salt=salt)
            aesgcm = AESGCM(key)
            pt = aesgcm.decrypt(nonce, ct, None)
            log_operation(logger, "Decrypt", status="SUCCESS", details=f"kdf={meta.get('kdf')}")
            return pt
        except Exception as e:
            log_operation(logger, "Decrypt", status="FAILED", details=str(e))
            raise
