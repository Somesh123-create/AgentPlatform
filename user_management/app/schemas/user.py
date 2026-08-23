from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, field_validator

from app.utils.password import validate_password_length


class UserCreate(BaseModel):

    name: str
    email: EmailStr
    password: str

    @field_validator("password")
    @classmethod
    def validate_password(cls, password: str) -> str:
        return validate_password_length(password)


class UserResponse(BaseModel):

    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    email: EmailStr
    role: str
    created_at: datetime
