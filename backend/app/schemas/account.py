from uuid import UUID

import re
from pydantic import BaseModel, Field, field_validator

_EMAIL_PATTERN = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")


class OrganizationRegistrationRequest(BaseModel):
    full_name: str = Field(..., min_length=1, max_length=255)
    email: str = Field(..., min_length=3, max_length=320)
    phone: str = Field(..., min_length=10, max_length=10, pattern=r"^[0-9]{10}$")
    organization_name: str = Field(..., min_length=1, max_length=255)
    password: str = Field(..., min_length=8, max_length=256)

    @field_validator("email")
    @classmethod
    def validate_email(cls, value: str) -> str:
        normalized = value.strip().lower()
        if not _EMAIL_PATTERN.fullmatch(normalized):
            raise ValueError("A valid email address is required")
        return normalized


class OrganizationRegistrationResponse(BaseModel):
    organization_id: UUID
    administrator_id: UUID
    organization_name: str
    email: str


class AdministratorTokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    onboarding_completed: bool


class PasswordLoginRequest(BaseModel):
    email: str = Field(..., min_length=3, max_length=320)
    password: str = Field(..., min_length=1, max_length=256)

    @field_validator("email")
    @classmethod
    def validate_email(cls, value: str) -> str:
        normalized = value.strip().lower()
        if not _EMAIL_PATTERN.fullmatch(normalized):
            raise ValueError("A valid email address is required")
        return normalized


class CurrentUserResponse(BaseModel):
    administrator_id: UUID
    organization_id: UUID
    organization_name: str
    full_name: str
    email: str
    phone: str
    role: str
    onboarding_completed: bool
