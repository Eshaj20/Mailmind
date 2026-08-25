from base64 import urlsafe_b64encode
from hashlib import sha256

from cryptography.fernet import Fernet

from app.core.config import settings

# The _fernet function generates a Fernet encryption object using a key derived from the application's secret key. It uses SHA-256 to hash the secret key and then encodes it in a URL-safe base64 format. This Fernet object is used for encrypting and decrypting sensitive data within the application.
def _fernet() -> Fernet:
    key = urlsafe_b64encode(sha256(settings.secret_key.encode("utf-8")).digest())
    return Fernet(key)


def encrypt_value(value: str) -> str:
    return _fernet().encrypt(value.encode("utf-8")).decode("utf-8")


def decrypt_value(value: str) -> str:
    return _fernet().decrypt(value.encode("utf-8")).decode("utf-8")
