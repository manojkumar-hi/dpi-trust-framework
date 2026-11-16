from uuid import UUID

import re
from typing import Literal
from pydantic import BaseModel, Field, field_validator, model_validator

_EMAIL_PATTERN = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")
_CIN_PATTERN = re.compile(r"^[LU][0-9]{5}[A-Z]{2}[0-9]{4}[A-Z]{3}[0-9]{6}$")
_WEBSITE_PATTERN = re.compile(r"^https?://[^\s]+$", re.IGNORECASE)

OrganizationType = Literal[
    "Private Limited",
    "Public Limited",
    "LLP",
    "Partnership",
    "Proprietorship",
    "Trust / Society",
    "Government",
    "Other",
]


class OrganizationRegistrationRequest(BaseModel):
    full_name: str = Field(..., min_length=1, max_length=255)
    email: str = Field(..., min_length=3, max_length=320)
    phone: str = Field(..., min_length=10, max_length=10, pattern=r"^[0-9]{10}$")
    organization_name: str = Field(..., min_length=1, max_length=255)
    organization_type: OrganizationType
    cin: str | None = Field(default=None, max_length=21)
    website: str | None = Field(default=None, max_length=500)
    password: str = Field(..., min_length=8, max_length=256)

    @field_validator("email")
    @classmethod
    def validate_email(cls, value: str) -> str:
        normalized = value.strip().lower()
        if not _EMAIL_PATTERN.fullmatch(normalized):
            raise ValueError("A valid email address is required")
        return normalized

    @field_validator("cin")
    @classmethod
    def validate_cin(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip().upper()
        if not _CIN_PATTERN.fullmatch(normalized):
            raise ValueError("Enter a valid 21-character CIN")
        return normalized

    @field_validator("website")
    @classmethod
    def validate_website(cls, value: str | None) -> str | None:
        if value is None or not value.strip():
            return None
        normalized = value.strip()
        if not _WEBSITE_PATTERN.fullmatch(normalized):
            raise ValueError("Website must start with http:// or https://")
        return normalized

    @model_validator(mode="after")
    def validate_company_cin(self) -> "OrganizationRegistrationRequest":
        company_types = {"Private Limited", "Public Limited"}
        if self.organization_type in company_types and self.cin is None:
            raise ValueError("CIN is required for Private Limited and Public Limited companies")
        if self.organization_type not in company_types and self.cin is not None:
            raise ValueError("CIN is only applicable to Private Limited and Public Limited companies")
        return self


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
