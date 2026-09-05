from collections.abc import AsyncGenerator

from fastapi import Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from agent_auth.dependencies import create_auth_dependency

from app.core.database import database
from app.core.security import jwt_manager
from app.models.user import User
from app.repositories.user_repository import UserRepository


agent_current_user = create_auth_dependency(
    jwt_manager,
    token_url="/auth/login",
)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async for session in database.session():
        yield session


async def get_current_user(
        current_user=Depends(agent_current_user),
        db: AsyncSession = Depends(get_db),
    ) -> User:
    user = await UserRepository(db).get_by_id(current_user.user_id)
    if user is None:
        raise HTTPException(
            status_code=401,
            detail="User not found.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return user
    