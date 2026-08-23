from app.core.security import create_access_token
from app.models.user import User
from app.repositories.user_repository import UserRepository
from app.utils.password import verify_password


class AuthService:
    def __init__(self, user_repository: UserRepository):
        self.user_repository = user_repository

    async def authenticate_user(self, email: str, password: str) -> str:
        user = await self.user_repository.get_by_email(email)
        if not user or not verify_password(password, user.password_hash):
            raise ValueError("Invalid email or password.")
        
        access_token = create_access_token(user.id)
        return access_token