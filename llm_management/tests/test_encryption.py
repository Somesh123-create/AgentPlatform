import os
from cryptography.fernet import Fernet
os.environ.setdefault("POSTGRES_DB", "test")
os.environ.setdefault("POSTGRES_USER", "test")
os.environ.setdefault("POSTGRES_PASSWORD", "test")
os.environ.setdefault("JWT_SECRET_KEY", "test")
os.environ.setdefault("LLM_ENCRYPTION_KEY", Fernet.generate_key().decode())
from app.core.encryption import decrypt_secret, encrypt_secret

def test_secret_round_trip_and_ciphertext_differs():
    secret = "provider-api-key"
    ciphertext = encrypt_secret(secret)
    assert ciphertext != secret
    assert decrypt_secret(ciphertext) == secret
