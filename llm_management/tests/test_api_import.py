import os
from cryptography.fernet import Fernet
os.environ.setdefault("POSTGRES_DB", "test")
os.environ.setdefault("POSTGRES_USER", "test")
os.environ.setdefault("POSTGRES_PASSWORD", "test")
os.environ.setdefault("JWT_SECRET_KEY", "test")
os.environ.setdefault("LLM_ENCRYPTION_KEY", Fernet.generate_key().decode())

def test_app_imports():
    from app.main import app
    assert any(getattr(route, "path", None) == "/health" for route in app.routes)


def test_swagger_uses_central_email_password_login():
    from app.main import app

    schemes = app.openapi()["components"]["securitySchemes"]
    assert schemes["OAuth2PasswordBearer"]["type"] == "oauth2"
    assert schemes["OAuth2PasswordBearer"]["flows"]["password"]["tokenUrl"] == "http://localhost:8000/auth/login"
