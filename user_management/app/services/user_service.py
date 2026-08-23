from app.models.user import User
from app.repositories.user_repository import UserRepository
from app.schemas.user import UserCreate
from app.utils.password import hash_password



class UserService:
    def __init__(self, user_repository: UserRepository):
        self.user_repository = user_repository

    async def create_user(self, user_create: UserCreate) -> User:
        existing_user = await self.user_repository.get_by_email(user_create.email)
        if existing_user:
            raise ValueError("User with this email already exists.")
        
        user = User(
            name=user_create.name,
            email=user_create.email,
            password_hash=hash_password(user_create.password),
            role="USER"  # Default role
        )
        return await self.user_repository.create(user)

    async def get_user_by_id(self, user_id: int) -> User:
        user = await self.user_repository.get_by_id(user_id)
        if not user:
            raise ValueError("User not found.")
        return user

    async def delete_user(self, user_id: int) -> str:
        delete_message = await self.user_repository.delete(user_id)
        if delete_message is None:
            raise ValueError("User not found.")
        return delete_message
        