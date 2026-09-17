from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User


class UserRepository:

    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_by_id(
            self,
            user_id: int,
        ) -> User | None:

        result = await self.db.execute(
            select(User).where(User.id == user_id)
        )

        return result.scalar_one_or_none()

    async def get_by_email(
            self,
            email: str,
        ) -> User | None:

        result = await self.db.execute(
            select(User).where(User.email == email)
        )

        return result.scalar_one_or_none()

    async def create(
            self,
            user: User,
        ) -> User:

        self.db.add(user)

        await self.db.commit()
        await self.db.refresh(user)

        return user

    async def update(
            self,
            user: User,
        ) -> User:

        await self.db.commit()
        await self.db.refresh(user)
        return user
    

    async def delete(
            self,
            user_id: int,
        ) -> None:

        user = await self.get_by_id(user_id)
        if not user:
            raise ValueError("User not found.")
        try:
            await self.db.delete(user)
            await self.db.commit()
            return "User deleted successfully."
        except Exception as e:
            await self.db.rollback()
            return f"Error deleting user: {str(e)}"