from agent_auth import JWTManager
from agent_auth.dependencies import create_auth_dependency

from app.core.config import settings


jwt_manager = JWTManager(
    secret_key=settings.jwt_secret_key,
    algorithm=settings.jwt_algorithm,
    access_token_expire_minutes=settings.jwt_access_token_expire_minutes,
)

current_user = create_auth_dependency(
    jwt_manager,
    token_url=settings.auth_token_url,
)