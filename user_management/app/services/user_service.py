from app.models.user import User
from app.repositories.user_repository import UserRepository
from app.schemas.user import PasswordUpdate, UserCreate, UserUpdate
from app.utils.password import hash_password, verify_password



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

    async def update_profile(self, user: User, user_update: UserUpdate) -> User:
        if user_update.email and user_update.email != user.email:
            existing_user = await self.user_repository.get_by_email(user_update.email)
            if existing_user and existing_user.id != user.id:
                raise ValueError("User with this email already exists.")

        if user_update.name is not None:
            user.name = user_update.name
        if user_update.email is not None:
            user.email = user_update.email

        return await self.user_repository.update(user)

    async def update_password(self, user: User, password_update: PasswordUpdate) -> User:
        if not verify_password(password_update.current_password, user.password_hash):
            raise ValueError("Current password is incorrect.")

        user.password_hash = hash_password(password_update.new_password)
        return await self.user_repository.update(user)

    async def delete_user(self, user_id: int) -> str:
        delete_message = await self.user_repository.delete(user_id)
        if delete_message is None:
            raise ValueError("User not found.")
        return delete_message
        