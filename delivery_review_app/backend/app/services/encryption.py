import base64
import hashlib

from cryptography.fernet import Fernet

from app.core.config import settings


key_material = hashlib.sha256(settings.encryption_key.encode()).digest()
fernet = Fernet(base64.urlsafe_b64encode(key_material))


def encrypt_value(raw: str) -> str:
    return fernet.encrypt(raw.encode()).decode()


def decrypt_value(token: str) -> str:
    return fernet.decrypt(token.encode()).decode()
