from agent_auth import JWTManager

from app.core.config import settings


jwt_manager = JWTManager(
    secret_key=settings.jwt_secret_key,
    algorithm=settings.jwt_algorithm,
    access_token_expire_minutes=settings.jwt_access_token_expire_minutes,
)


def create_access_token(user_id: int, role: str) -> str:
    """Create a JWT access token for the given user ID.

    Uses the shared agent-auth JWTManager for token creation.
    """
    return jwt_manager.create_access_token(user_id=user_id, role=role)


def decode_access_token(token: str) -> int | None:
    """Decode a JWT access token and return the user ID.

    Uses the shared agent-auth JWTManager for token decoding.
    """
    payload = jwt_manager.decode_access_token(token)
    if payload is None:
        return None

    subject = payload.get("sub")
    if subject is None:
        return None

    try:
        user_id = int(subject)
    except (TypeError, ValueError):
        return None

    return user_id if user_id > 0 else None