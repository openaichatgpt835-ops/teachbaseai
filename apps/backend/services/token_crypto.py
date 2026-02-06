"""Шифрование токенов порталов (AES)."""
import base64
import hashlib
import os
from typing import Optional

from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC


def _get_fernet(secret: str) -> Fernet:
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=b"teachbaseai_tokens",
        iterations=100000,
    )
    key = base64.urlsafe_b64encode(kdf.derive(secret.encode()))
    return Fernet(key)


def encrypt_token(plain: str, encryption_key: str) -> str:
    if not plain:
        return ""
    f = _get_fernet(encryption_key)
    return f.encrypt(plain.encode()).decode()


def decrypt_token(cipher: str, encryption_key: str) -> Optional[str]:
    if not cipher:
        return None
    try:
        f = _get_fernet(encryption_key)
        return f.decrypt(cipher.encode()).decode()
    except Exception:
        return None


def mask_token(token: Optional[str]) -> str:
    if not token or len(token) < 4:
        return "****"
    return "****" + token[-4:]
