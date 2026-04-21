from pydantic import BaseModel, EmailStr, Field

from app.models.user import UserRole


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=6)
    name: str = Field(min_length=1, max_length=100)
    department: str | None = None
    verification_code: str = Field(min_length=4, max_length=12)


class SendRegisterCodeRequest(BaseModel):
    email: EmailStr


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class UserOut(BaseModel):
    id: int
    email: EmailStr
    name: str
    role: UserRole
    department: str | None = None
    avatar_url: str | None = None

    class Config:
        from_attributes = True
