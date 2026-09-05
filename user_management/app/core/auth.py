from agent_auth import JWTManager

from app.core.config import settings


jwt_manager = JWTManager(
    secret_key=settings.jwt_secret_key,
    algorithm=settings.jwt_algorithm,
    access_token_expire_minutes=(
        settings.jwt_access_token_expire_minutes
    ),
)