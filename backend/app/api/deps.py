"""Reusable authentication and RBAC dependency injection providers."""

import uuid
from collections.abc import Callable

from fastapi import Depends, Header, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import ForbiddenError, UnauthorizedError
from app.core.security import verify_access_token
from app.infrastructure.database.models import User, UserRole
from app.infrastructure.database.session import get_db_session
from app.repositories.user_repository import UserRepository


async def get_token_from_header_or_cookie(
    request: Request,
    authorization: str | None = Header(default=None),
) -> str:
    """Extracts JWT bearer token from Authorization header or cookie."""
    if authorization and authorization.lower().startswith("bearer "):
        return authorization[7:].strip()

    # Fallback to access_token cookie if present
    cookie_token = request.cookies.get("access_token")
    if cookie_token:
        return cookie_token

    raise UnauthorizedError("Authentication credentials were not provided", code="AUTHENTICATION_REQUIRED")


async def get_current_user(
    token: str = Depends(get_token_from_header_or_cookie),
    session: AsyncSession = Depends(get_db_session),
) -> User:
    """Validates JWT access token and resolves current authenticated User entity."""
    payload = verify_access_token(token)
    user_id_str = payload.get("sub")
    if not user_id_str:
        raise UnauthorizedError("Invalid token subject", code="INVALID_TOKEN_SUBJECT")

    try:
        user_id = uuid.UUID(user_id_str)
    except ValueError:
        raise UnauthorizedError("Malformed user identifier in token", code="MALFORMED_USER_ID") from None

    user_repo = UserRepository(session)
    user = await user_repo.get_by_id(user_id)

    if not user:
        raise UnauthorizedError("User does not exist or has been deleted", code="USER_NOT_FOUND")

    if not user.is_active:
        raise UnauthorizedError("User account is deactivated", code="ACCOUNT_DEACTIVATED")

    return user


def require_role(*allowed_roles: str) -> Callable[[User], User]:
    """Factory creating an authorization dependency enforcing role membership."""

    def role_checker(user: User = Depends(get_current_user)) -> User:
        if user.role not in allowed_roles:
            raise ForbiddenError(
                f"Access denied: Required role '{allowed_roles}' but user possesses '{user.role}'",
                code="FORBIDDEN_INSUFFICIENT_ROLE",
                details={"required_roles": list(allowed_roles), "user_role": user.role},
            )
        return user

    return role_checker


# Shortcuts
require_authenticated_user = get_current_user
require_admin = require_role(UserRole.ADMIN.value)
