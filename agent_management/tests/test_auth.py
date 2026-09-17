import asyncio

from agent_auth import JWTManager
from app.core.auth import current_user, jwt_manager


def test_shared_jwt_configuration():
    assert jwt_manager.algorithm == "HS256"
    assert callable(current_user)


def test_valid_token_claims():
    token = jwt_manager.create_access_token(42, "USER")
    user = asyncio.run(current_user(token))
    assert user.user_id == 42


def test_swagger_uses_central_email_password_login():
    from app.main import app

    schemes = app.openapi()["components"]["securitySchemes"]
    assert schemes["OAuth2PasswordBearer"]["type"] == "oauth2"
    assert schemes["OAuth2PasswordBearer"]["flows"]["password"]["tokenUrl"] == "http://localhost:8000/auth/login"
