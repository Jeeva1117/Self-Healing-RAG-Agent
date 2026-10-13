"""Authentication and user management request/response Pydantic schemas."""

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class UserRegisterRequest(BaseModel):
    """Schema for user registration."""

    email: EmailStr = Field(..., description="User's unique email address")
    password: str = Field(..., min_length=8, max_length=128, description="User password")
    name: str = Field(..., min_length=1, max_length=150, description="Full or display name")


class UserLoginRequest(BaseModel):
    """Schema for user credentials login."""

    email: EmailStr = Field(..., description="Account email address")
    password: str = Field(..., description="Account password")


class RefreshTokenRequest(BaseModel):
    """Schema for manual refresh token submission when cookies are not utilized."""

    refresh_token: str | None = Field(default=None, description="Cryptographic refresh token")


class ChangePasswordRequest(BaseModel):
    """Schema for changing password."""

    current_password: str = Field(..., description="Existing account password")
    new_password: str = Field(..., min_length=8, max_length=128, description="New account password")


class ForgotPasswordRequest(BaseModel):
    """Schema for requesting password reset."""

    email: EmailStr = Field(..., description="Account email address")


class UserResponse(BaseModel):
    """Safe public representation of user identity."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID = Field(..., description="Unique user identifier")
    email: str = Field(..., description="User email address")
    name: str = Field(..., description="User display name")
    role: str = Field(..., description="User RBAC role")
    is_active: bool = Field(..., description="Active status")
    is_verified: bool = Field(..., description="Email verified status")
    created_at: datetime = Field(..., description="Account creation timestamp")
    last_login_at: datetime | None = Field(default=None, description="Last login timestamp")


class TokenResponse(BaseModel):
    """Access token grant response."""

    access_token: str = Field(..., description="Signed JWT access token")
    token_type: str = Field(default="bearer", description="Token type")
    expires_in: int = Field(..., description="Access token expiration duration in seconds")
    user: UserResponse = Field(..., description="Authenticated user profile")


class SessionResponse(BaseModel):
    """Active session information for security auditing."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID = Field(..., description="Session identifier")
    created_at: datetime = Field(..., description="Session creation timestamp")
    expires_at: datetime = Field(..., description="Session expiry timestamp")
    last_used_at: datetime | None = Field(default=None, description="Last activity timestamp")
    user_agent: str | None = Field(default=None, description="Client device / browser user-agent")
    ip_address: str | None = Field(default=None, description="Client IP address")
    is_current: bool = Field(default=False, description="Whether this session matches current request")


class AdminUserListResponse(BaseModel):
    """Paginated list of users for administrator management."""

    users: list[UserResponse] = Field(..., description="List of users")
    total: int = Field(..., description="Total count of users")
