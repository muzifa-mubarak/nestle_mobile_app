import re

from pydantic import BaseModel, EmailStr, Field, field_validator


def _password_ok(value: str) -> str:
    if not (8 <= len(value) <= 72) or not re.search(r"[A-Z]", value) or not re.search(r"[a-z]", value) or not re.search(r"\d", value):
        raise ValueError("Use 8–72 characters with an uppercase letter, a lowercase letter, and a digit.")
    return value


class RegisterRequest(BaseModel):
    full_name: str = Field(min_length=2, max_length=100)
    email: EmailStr
    organization: str = Field(min_length=2, max_length=150)
    password: str
    accepted_terms: bool

    @field_validator("password")
    @classmethod
    def password_policy(cls, value: str) -> str:
        return _password_ok(value)


class SocialRequest(BaseModel):
    provider: str
    full_name: str = Field(min_length=2, max_length=100)
    email: EmailStr
    accepted_terms: bool
    device_info: str | None = None

    @field_validator("provider")
    @classmethod
    def known_provider(cls, value: str) -> str:
        provider = value.strip().lower()
        if provider not in {"google", "apple"}:
            raise ValueError("Choose Google or Apple.")
        return provider


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=72)
    device_info: str | None = None


class VerifyEmailRequest(BaseModel):
    email: EmailStr
    code: str = Field(min_length=6, max_length=6)
    device_info: str | None = None


class EmailRequest(BaseModel):
    email: EmailStr


class RefreshRequest(BaseModel):
    refresh_token: str


class LogoutRequest(BaseModel):
    refresh_token: str | None = None


class ResetPasswordRequest(BaseModel):
    email: EmailStr
    code: str = Field(min_length=6, max_length=6)
    new_password: str

    @field_validator("new_password")
    @classmethod
    def password_policy(cls, value: str) -> str:
        return _password_ok(value)
