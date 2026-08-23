from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_current_user
from app.core.database import get_db
from app.repositories.user_repository import UserRepository
from app.schemas.user import UserResponse
from app.services.user_service import UserService


router = APIRouter(
    prefix="/users",
    tags=["Users"],
)


@router.get("/me", response_model=UserResponse)
async def get_current_user_info(
        current_user: Annotated[UserResponse, Depends(get_current_user)],
    ):
    return current_user


@router.get("/{user_id}", response_model=UserResponse)
async def get_user_by_id(
        user_id: int,
        current_user: Annotated[UserResponse, Depends(get_current_user)],
        db: Annotated[AsyncSession, Depends(get_db)],
    ):
    user_repo = UserRepository(db)
    user_service = UserService(user_repo)
    
    user = await user_service.get_user_by_id(user_id)
    
    if not user:
        raise HTTPException(status_code=404, detail="User not found.")
    
    return user