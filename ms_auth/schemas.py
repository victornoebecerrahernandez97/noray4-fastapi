from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    display_name: str = Field(min_length=2, max_length=60)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=128)


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class GuestTokenRequest(BaseModel):
    nickname: str = Field(min_length=3, max_length=40)

    @field_validator("nickname")
    @classmethod
    def strip_and_validate(cls, v: str) -> str:
        stripped = v.strip()
        if len(stripped) < 3:
            raise ValueError("El apodo debe tener al menos 3 caracteres sin espacios al inicio y fin")
        return stripped


class GuestTokenResponse(TokenResponse):
    display_name: str


class UserOut(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    id: str = Field(alias="_id")
    email: EmailStr
    display_name: str
    is_guest: bool
    is_active: bool
