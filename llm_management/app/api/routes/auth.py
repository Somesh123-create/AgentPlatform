from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import jwt_manager
from app.db.session import get_db


router = APIRouter(
    prefix="/auth",
    tags=["Authentication"],
)


@router.post("/login", response_model=dict)
async def login(
    form_data: Annotated[OAuth2PasswordRequestForm, Depends()],
    db: AsyncSession = Depends(get_db),
):
    """Login endpoint for Swagger UI OAuth2 authentication."""
    user = await jwt_manager.verify(
        email=form_data.username,
        password=form_data.password,
    )
    if not user:
        raise HTTPException(status_code=401, detail="Invalid email or password.")

    access_token = jwt_manager.create_access_token(
        subject={"user_id": user.id, "email": user.email}
    )

    return {"access_token": access_token, "token_type": "bearer"}