"""Key Derivation Utilities (Argon2id default, PBKDF2 fallback)
ตามข้อกำหนดบทที่ 1: ใช้ Argon2id เป็น KDF หลัก (RFC 9106 / OWASP)
"""
import os
from typing import Tuple

from utils.logger import setup_logger
try:
    from config import CRYPTO_SETTINGS  # expects salt_bytes, argon2id{}, pbkdf2{}
except Exception:
    # Fallback defaults
    CRYPTO_SETTINGS = {
        "salt_bytes": 16,
        "argon2id": {"time_cost": 3, "memory_cost": 64 * 1024, "parallelism": 2, "key_len": 32},
        "pbkdf2": {"iterations": 300_000, "key_len": 32},
    }

logger = setup_logger(__name__)

try:
    from argon2.low_level import hash_secret_raw, Type
    HAVE_ARGON2 = True
except Exception:
    HAVE_ARGON2 = False

try:
    from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
    from cryptography.hazmat.primitives import hashes
except Exception:
    PBKDF2HMAC = None  # type: ignore


def derive_key(password: str, salt: bytes = None) -> Tuple[bytes, bytes, dict]:
    """Derive a key from a password.
    Returns: (key, salt, params_dict)
    """
    if salt is None:
        salt = os.urandom(CRYPTO_SETTINGS.get('salt_bytes', 16))

    if HAVE_ARGON2:
        params = CRYPTO_SETTINGS.get('argon2id', {})
        time_cost = params.get('time_cost', 3)
        memory_cost = params.get('memory_cost', 64 * 1024)  # KiB
        parallelism = params.get('parallelism', 2)
        key_len = params.get('key_len', 32)
        key = hash_secret_raw(
            password.encode('utf-8'),
            salt,
            time_cost=time_cost,
            memory_cost=memory_cost,
            parallelism=parallelism,
            hash_len=key_len,
            type=Type.ID,
        )
        meta = {
            'kdf': 'argon2id',
            'time_cost': time_cost,
            'memory_cost': memory_cost,
            'parallelism': parallelism,
            'key_len': key_len,
        }
        return key, salt, meta
    else:
        # Fallback: PBKDF2-HMAC-SHA256
        if PBKDF2HMAC is None:
            raise RuntimeError("No KDF available: install 'argon2-cffi' or cryptography PBKDF2.")
        iterations = CRYPTO_SETTINGS.get('pbkdf2', {}).get('iterations', 300_000)
        key_len = CRYPTO_SETTINGS.get('pbkdf2', {}).get('key_len', 32)
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=key_len,
            salt=salt,
            iterations=iterations,
        )
        key = kdf.derive(password.encode('utf-8'))
        meta = {
            'kdf': 'pbkdf2',
            'iterations': iterations,
            'key_len': key_len,
        }
        logger.warning("Using PBKDF2 fallback (install 'argon2-cffi' to use Argon2id).");
        return key, salt, meta
