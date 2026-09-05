from agent_auth import authenticate_user

from app.core.security import jwt_manager
from app.models.user import User
from app.repositories.user_repository import UserRepository


class AuthService:
    def __init__(self, user_repository: UserRepository):
        self.user_repository = user_repository

    async def authenticate_user(self, email: str, password: str) -> str:
        async def load_user(identifier: str) -> User | None:
            return await self.user_repository.get_by_email(identifier)

        return await authenticate_user(
            email,
            password,
            load_user,
            jwt_manager,
            get_role=lambda user: str(getattr(user.role, "value", user.role)),
        )