from pydantic import BaseModel, ConfigDict, EmailStr, field_validator

from app.utils.password import validate_password_length


class LoginRequest(BaseModel):

    email: EmailStr
    password: str

    @field_validator("password")
    @classmethod
    def validate_password(cls, password: str) -> str:
        return validate_password_length(password)


class TokenResponse(BaseModel):

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxIiwiZXhwIjoxNzg3NDQ5NTkwfQ.vbyevtjDMWym9FRE2k24ehf55HxTopbeNUY7-gPo32I",
                "token_type": "bearer",
            }
        }
    )

    access_token: str
    token_type: str = "bearer"