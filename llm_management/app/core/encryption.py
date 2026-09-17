from cryptography.fernet import Fernet
from app.core.config import settings

_cipher = Fernet(settings.llm_encryption_key.encode())


def encrypt_secret(value: str) -> str:
    return _cipher.encrypt(value.encode()).decode()


def decrypt_secret(value: str) -> str:
    return _cipher.decrypt(value.encode()).decode()
