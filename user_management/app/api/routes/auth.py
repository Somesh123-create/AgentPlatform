from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.repositories.user_repository import UserRepository
from app.schemas.auth import LoginRequest, TokenResponse
from app.schemas.user import UserCreate, UserResponse
from app.services.auth_service import AuthService
from app.services.user_service import UserService


router = APIRouter(
    prefix="/auth",
    tags=["Authentication"],
)


@router.post("/register", response_model=UserResponse)
async def register_user(
        user_create: UserCreate,
        db: Annotated[AsyncSession, Depends(get_db)],
    ):
    user_repo = UserRepository(db)
    user_service = UserService(user_repo)
    
    try:
        user = await user_service.create_user(user_create)
        return user
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    

@router.post("/login", response_model=TokenResponse)
async def login_user(
        form_data: Annotated[OAuth2PasswordRequestForm, Depends()],
        db: Annotated[AsyncSession, Depends(get_db)],
    ):
    user_repo = UserRepository(db)
    auth_service = AuthService(user_repo)

    email = form_data.username
    password = form_data.password

    try:
        access_token = await auth_service.authenticate_user(email, password)

        if not access_token:
            raise HTTPException(status_code=401, detail="Invalid email or password.")

        return TokenResponse(access_token=access_token)
    except ValueError as e:
        raise HTTPException(status_code=401, detail=str(e))