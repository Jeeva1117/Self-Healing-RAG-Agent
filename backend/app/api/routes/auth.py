"""Authentication and user session management REST endpoints."""

import uuid
from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, Depends, Request, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.config import settings
from app.infrastructure.database.models import User
from app.infrastructure.database.session import get_db_session
from app.schemas.auth import (
    ChangePasswordRequest,
    ForgotPasswordRequest,
    RefreshTokenRequest,
    SessionResponse,
    TokenResponse,
    UserLoginRequest,
    UserRegisterRequest,
    UserResponse,
)
from app.schemas.common import ApiResponse, MetaInfo
from app.services.auth_service import AuthService

router = APIRouter(prefix="/auth", tags=["Authentication & Identity"])


def _create_meta(request: Request) -> MetaInfo:
    request_id = getattr(request.state, "request_id", None)
    return MetaInfo(request_id=request_id, timestamp=datetime.now(UTC).isoformat())


@router.post(
    "/register",
    response_model=ApiResponse[UserResponse],
    status_code=status.HTTP_201_CREATED,
    summary="Register a new user account",
)
async def register(
    request: Request,
    payload: UserRegisterRequest,
    session: AsyncSession = Depends(get_db_session),
) -> ApiResponse[UserResponse]:
    """Registers a new user with email, name, and password."""
    auth_service = AuthService(session)
    user = await auth_service.register(
        email=payload.email,
        password=payload.password,
        name=payload.name,
        ip_address=request.client.host if request.client else None,
        request_id=getattr(request.state, "request_id", None),
    )
    return ApiResponse(
        success=True,
        data=UserResponse.model_validate(user),
        meta=_create_meta(request),
    )


@router.post(
    "/login",
    response_model=ApiResponse[TokenResponse],
    summary="Authenticate user and obtain JWT tokens",
)
async def login(
    request: Request,
    response: Response,
    payload: UserLoginRequest,
    session: AsyncSession = Depends(get_db_session),
) -> ApiResponse[TokenResponse]:
    """Authenticates credentials, returns short-lived access token and sets secure refresh cookie."""
    auth_service = AuthService(session)
    user, access_token, raw_refresh, expires_in = await auth_service.login(
        email=payload.email,
        password=payload.password,
        user_agent=request.headers.get("user-agent"),
        ip_address=request.client.host if request.client else None,
        request_id=getattr(request.state, "request_id", None),
    )

    # Set secure HttpOnly cookie for refresh token
    response.set_cookie(
        key=settings.COOKIE_NAME_REFRESH,
        value=raw_refresh,
        max_age=settings.JWT_REFRESH_TOKEN_EXPIRE_DAYS * 86400,
        httponly=True,
        secure=settings.COOKIE_SECURE,
        samesite=settings.COOKIE_SAMESITE,
        path="/",
    )

    token_data = TokenResponse(
        access_token=access_token,
        token_type="bearer",
        expires_in=expires_in,
        user=UserResponse.model_validate(user),
    )
    return ApiResponse(
        success=True,
        data=token_data,
        meta=_create_meta(request),
    )


@router.post(
    "/refresh",
    response_model=ApiResponse[TokenResponse],
    summary="Rotate refresh token and issue new access token",
)
async def refresh_token(
    request: Request,
    response: Response,
    body: RefreshTokenRequest | None = None,
    session: AsyncSession = Depends(get_db_session),
) -> ApiResponse[TokenResponse]:
    """Refreshes session using HttpOnly cookie or request body, enforcing rotation."""
    raw_refresh = None
    if body and body.refresh_token:
        raw_refresh = body.refresh_token
    else:
        raw_refresh = request.cookies.get(settings.COOKIE_NAME_REFRESH)

    auth_service = AuthService(session)
    user, new_access_token, new_raw_refresh, expires_in = await auth_service.refresh_session(
        raw_refresh_token=raw_refresh,
        user_agent=request.headers.get("user-agent"),
        ip_address=request.client.host if request.client else None,
        request_id=getattr(request.state, "request_id", None),
    )

    # Rotate HttpOnly cookie
    response.set_cookie(
        key=settings.COOKIE_NAME_REFRESH,
        value=new_raw_refresh,
        max_age=settings.JWT_REFRESH_TOKEN_EXPIRE_DAYS * 86400,
        httponly=True,
        secure=settings.COOKIE_SECURE,
        samesite=settings.COOKIE_SAMESITE,
        path="/",
    )

    token_data = TokenResponse(
        access_token=new_access_token,
        token_type="bearer",
        expires_in=expires_in,
        user=UserResponse.model_validate(user),
    )
    return ApiResponse(
        success=True,
        data=token_data,
        meta=_create_meta(request),
    )


@router.post(
    "/logout",
    response_model=ApiResponse[dict],
    summary="Revoke active refresh token session",
)
async def logout(
    request: Request,
    response: Response,
    body: RefreshTokenRequest | None = None,
    session: AsyncSession = Depends(get_db_session),
) -> ApiResponse[dict]:
    """Revokes current session and clears refresh cookie."""
    raw_refresh = (body.refresh_token if body else None) or request.cookies.get(settings.COOKIE_NAME_REFRESH)
    auth_service = AuthService(session)
    await auth_service.logout(
        raw_refresh_token=raw_refresh,
        ip_address=request.client.host if request.client else None,
        request_id=getattr(request.state, "request_id", None),
    )

    # Invalidate cookie in browser client
    response.delete_cookie(
        key=settings.COOKIE_NAME_REFRESH,
        path="/",
        httponly=True,
        secure=settings.COOKIE_SECURE,
        samesite=settings.COOKIE_SAMESITE,
    )

    return ApiResponse(
        success=True,
        data={"message": "Successfully logged out"},
        meta=_create_meta(request),
    )


@router.post(
    "/logout-all",
    response_model=ApiResponse[dict],
    summary="Revoke all active sessions across all devices",
)
async def logout_all(
    request: Request,
    response: Response,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> ApiResponse[dict]:
    """Revokes every active session for current user."""
    auth_service = AuthService(session)
    count = await auth_service.logout_all(
        user_id=current_user.id,
        ip_address=request.client.host if request.client else None,
        request_id=getattr(request.state, "request_id", None),
    )

    response.delete_cookie(
        key=settings.COOKIE_NAME_REFRESH,
        path="/",
        httponly=True,
        secure=settings.COOKIE_SECURE,
        samesite=settings.COOKIE_SAMESITE,
    )

    return ApiResponse(
        success=True,
        data={"message": f"Successfully revoked {count} active sessions"},
        meta=_create_meta(request),
    )


@router.get(
    "/me",
    response_model=ApiResponse[UserResponse],
    summary="Retrieve authenticated user profile",
)
async def get_me(
    request: Request,
    current_user: User = Depends(get_current_user),
) -> ApiResponse[UserResponse]:
    """Returns profile for currently authenticated user."""
    return ApiResponse(
        success=True,
        data=UserResponse.model_validate(current_user),
        meta=_create_meta(request),
    )


@router.post(
    "/change-password",
    response_model=ApiResponse[dict],
    summary="Change user password and revoke other sessions",
)
async def change_password(
    request: Request,
    response: Response,
    payload: ChangePasswordRequest,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> ApiResponse[dict]:
    """Validates existing password, sets new password, and revokes other active sessions."""
    auth_service = AuthService(session)
    await auth_service.change_password(
        user=current_user,
        current_password=payload.current_password,
        new_password=payload.new_password,
        ip_address=request.client.host if request.client else None,
        request_id=getattr(request.state, "request_id", None),
    )

    # Invalidate current refresh cookie since sessions were revoked
    response.delete_cookie(
        key=settings.COOKIE_NAME_REFRESH,
        path="/",
        httponly=True,
        secure=settings.COOKIE_SECURE,
        samesite=settings.COOKIE_SAMESITE,
    )

    return ApiResponse(
        success=True,
        data={"message": "Password changed successfully. Please log in again with new password."},
        meta=_create_meta(request),
    )


@router.get(
    "/sessions",
    response_model=ApiResponse[list[SessionResponse]],
    summary="List active sessions for current user",
)
async def list_sessions(
    request: Request,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> ApiResponse[list[SessionResponse]]:
    """Returns active sessions for user, indicating current session."""
    current_refresh = request.cookies.get(settings.COOKIE_NAME_REFRESH)
    auth_service = AuthService(session)
    sessions = await auth_service.list_user_sessions(current_user.id, current_refresh)
    session_responses = [SessionResponse.model_validate(s) for s in sessions]
    return ApiResponse(
        success=True,
        data=session_responses,
        meta=_create_meta(request),
    )


@router.delete(
    "/sessions/{session_id}",
    response_model=ApiResponse[dict],
    summary="Revoke a specific user session",
)
async def revoke_session(
    request: Request,
    session_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> ApiResponse[dict]:
    """Revokes a specific session belonging to current user."""
    auth_service = AuthService(session)
    await auth_service.revoke_user_session(
        user_id=current_user.id,
        session_id=session_id,
        ip_address=request.client.host if request.client else None,
        request_id=getattr(request.state, "request_id", None),
    )
    return ApiResponse(
        success=True,
        data={"message": "Session revoked successfully"},
        meta=_create_meta(request),
    )


@router.post(
    "/forgot-password",
    response_model=ApiResponse[dict],
    summary="Request password reset",
)
async def forgot_password(
    request: Request,
    payload: ForgotPasswordRequest,
) -> ApiResponse[dict]:
    """Truthfully informs that SMTP email infrastructure is not configured in this environment."""
    return ApiResponse(
        success=True,
        data={
            "status": "unconfigured",
            "message": (
                "Password reset email service is not configured with an SMTP email provider in this environment."
            ),
            "email": payload.email,
        },
        meta=_create_meta(request),
    )


@router.get(
    "/config",
    response_model=ApiResponse[dict[str, Any]],
    summary="Retrieve public authentication flags and environment status",
)
async def get_auth_config(
    request: Request,
) -> ApiResponse[dict[str, Any]]:
    """Returns safe, public authentication configuration flags such as whether demo login is available."""
    return ApiResponse(
        success=True,
        data={
            "demo_login_enabled": settings.is_demo_login_allowed,
            "environment": settings.effective_environment,
        },
        meta=_create_meta(request),
    )


@router.post(
    "/demo-login",
    response_model=ApiResponse[TokenResponse],
    summary="Authenticate as development demo user (development-only)",
)
async def demo_login(
    request: Request,
    response: Response,
    session: AsyncSession = Depends(get_db_session),
) -> ApiResponse[TokenResponse]:
    """Authenticates as the development demo user with real JWT access and refresh session tokens.

    Strictly disabled and returns 403 Forbidden when DEMO_LOGIN_ENABLED is False or in production.
    """
    auth_service = AuthService(session)
    user, access_token, raw_refresh, expires_in = await auth_service.demo_login(
        user_agent=request.headers.get("user-agent"),
        ip_address=request.client.host if request.client else None,
        request_id=getattr(request.state, "request_id", None),
    )

    # Set secure HttpOnly cookie for refresh token
    response.set_cookie(
        key=settings.COOKIE_NAME_REFRESH,
        value=raw_refresh,
        max_age=settings.JWT_REFRESH_TOKEN_EXPIRE_DAYS * 86400,
        httponly=True,
        secure=settings.COOKIE_SECURE,
        samesite=settings.COOKIE_SAMESITE,
        path="/",
    )

    token_data = TokenResponse(
        access_token=access_token,
        token_type="bearer",
        expires_in=expires_in,
        user=UserResponse.model_validate(user),
    )
    return ApiResponse(
        success=True,
        data=token_data,
        meta=_create_meta(request),
    )
