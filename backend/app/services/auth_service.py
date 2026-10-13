"""Authentication and authorization service implementing core business logic."""

import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.errors import ConflictError, ForbiddenError, NotFoundError, UnauthorizedError
from app.core.logging import get_logger
from app.core.security import (
    create_access_token,
    generate_secure_token,
    hash_password,
    hash_token,
    validate_password_strength,
    verify_password,
)
from app.infrastructure.database.models import User, UserRole
from app.repositories.audit_repository import AuditRepository
from app.repositories.session_repository import SessionRepository
from app.repositories.user_repository import UserRepository

logger = get_logger("app.services.auth")


class AuthService:
    """Service governing user authentication, session lifecycle, and RBAC authorization."""

    def __init__(self, session: AsyncSession):
        self.session = session
        self.user_repo = UserRepository(session)
        self.session_repo = SessionRepository(session)
        self.audit_repo = AuditRepository(session)

    async def register(
        self,
        email: str,
        password: str,
        name: str,
        ip_address: str | None = None,
        request_id: str | None = None,
    ) -> User:
        """Registers a new user account with secure password hashing and audit recording."""
        # 1. Enforce password complexity policy
        validate_password_strength(password)

        # 2. Check for unique email constraint (prevent duplicates)
        existing = await self.user_repo.get_by_email(email)
        if existing:
            await self.audit_repo.log_event(
                action="USER_REGISTER_CONFLICT",
                resource_type="user",
                status="failure",
                details={"email": email.strip().lower()},
                ip_address=ip_address,
                request_id=request_id,
            )
            raise ConflictError(
                "An account with this email address already exists",
                code="USER_ALREADY_EXISTS",
            )

        # 3. Hash password using Argon2id
        hashed_password = hash_password(password)

        # 4. If this is the first registered user in the database, promote to ADMIN; otherwise USER
        total_users = await self.user_repo.count_users()
        initial_role = UserRole.ADMIN.value if total_users == 0 else UserRole.USER.value

        user = await self.user_repo.create_user(
            email=email,
            name=name,
            password_hash=hashed_password,
            role=initial_role,
            is_active=True,
            is_verified=False,
        )

        # 5. Audit log event
        await self.audit_repo.log_event(
            action="USER_REGISTERED",
            resource_type="user",
            actor_id=str(user.id),
            resource_id=str(user.id),
            status="success",
            details={"email": user.email, "role": user.role},
            ip_address=ip_address,
            request_id=request_id,
        )

        logger.info(f"User registered successfully: id={user.id} role={user.role}")
        return user

    async def login(
        self,
        email: str,
        password: str,
        user_agent: str | None = None,
        ip_address: str | None = None,
        request_id: str | None = None,
    ) -> tuple[User, str, str, int]:
        """Authenticates user credentials and issues access JWT + rotated refresh token."""
        user = await self.user_repo.get_by_email(email)

        # Prevent timing enumeration attacks by verifying against dummy hash if user doesn't exist
        dummy_hash = "$argon2id$v=19$m=65536,t=2,p=1$c29tZXNhbHQAAAAAAAAAAA$q70X30f9tWn6d2vjKkZqLg"
        password_matches = verify_password(password, user.password_hash if user else dummy_hash)

        if not user or not password_matches:
            await self.audit_repo.log_event(
                action="USER_LOGIN_FAILED",
                resource_type="user",
                status="failure",
                details={"email": email.strip().lower(), "reason": "invalid_credentials"},
                ip_address=ip_address,
                request_id=request_id,
            )
            raise UnauthorizedError(
                "Invalid email or password",
                code="INVALID_CREDENTIALS",
            )

        if not user.is_active:
            await self.audit_repo.log_event(
                action="USER_LOGIN_BLOCKED",
                resource_type="user",
                actor_id=str(user.id),
                resource_id=str(user.id),
                status="failure",
                details={"reason": "account_deactivated"},
                ip_address=ip_address,
                request_id=request_id,
            )
            raise UnauthorizedError(
                "Account is deactivated. Please contact system administrator.",
                code="ACCOUNT_DEACTIVATED",
            )

        # Update last login timestamp
        await self.user_repo.update_last_login(user)

        # Generate tokens
        access_token = create_access_token(user.id, user.role)
        raw_refresh_token = generate_secure_token()
        token_family = str(uuid.uuid4())
        refresh_expires_at = datetime.now(UTC) + timedelta(days=settings.JWT_REFRESH_TOKEN_EXPIRE_DAYS)

        # Store session record with hashed token
        await self.session_repo.create_session(
            user_id=user.id,
            refresh_token_hash=hash_token(raw_refresh_token),
            token_family=token_family,
            expires_at=refresh_expires_at,
            user_agent=user_agent,
            ip_address=ip_address,
        )

        # Audit success
        await self.audit_repo.log_event(
            action="USER_LOGIN_SUCCESS",
            resource_type="user",
            actor_id=str(user.id),
            resource_id=str(user.id),
            status="success",
            details={"email": user.email, "role": user.role},
            ip_address=ip_address,
            request_id=request_id,
        )

        expires_in = settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES * 60
        return user, access_token, raw_refresh_token, expires_in

    async def refresh_session(
        self,
        raw_refresh_token: str | None,
        user_agent: str | None = None,
        ip_address: str | None = None,
        request_id: str | None = None,
    ) -> tuple[User, str, str, int]:
        """Rotates refresh token and issues a fresh access token with reuse detection."""
        if not raw_refresh_token:
            raise UnauthorizedError("Missing refresh token", code="REFRESH_TOKEN_MISSING")

        token_hash = hash_token(raw_refresh_token)
        session = await self.session_repo.get_by_token_hash(token_hash)

        if not session:
            raise UnauthorizedError("Invalid refresh token", code="INVALID_REFRESH_TOKEN")

        # REUSE DETECTION: If this token was already revoked, a compromised token is being reused!
        if session.revoked_at is not None:
            revoked_count = await self.session_repo.revoke_token_family(session.token_family)
            await self.audit_repo.log_event(
                action="TOKEN_REUSE_DETECTED",
                resource_type="user_session",
                actor_id=str(session.user_id),
                resource_id=str(session.id),
                status="failure",
                details={
                    "token_family": session.token_family,
                    "revoked_family_sessions_count": revoked_count,
                },
                ip_address=ip_address,
                request_id=request_id,
            )
            logger.warning(
                f"Refresh token reuse detected for user {session.user_id}! Revoked family {session.token_family}"
            )
            await self.session.commit()
            raise UnauthorizedError(
                "Security alert: Token reuse detected. All active sessions have been invalidated.",
                code="TOKEN_REUSE_DETECTED",
            )

        # Expiration check
        session_expires = session.expires_at
        if session_expires.tzinfo is None:
            session_expires = session_expires.replace(tzinfo=UTC)
        if session_expires <= datetime.now(UTC):
            await self.session_repo.revoke_session(session)
            raise UnauthorizedError(
                "Refresh token has expired. Please log in again.",
                code="REFRESH_TOKEN_EXPIRED",
            )

        # Invalidate the consumed refresh token
        await self.session_repo.revoke_session(session)

        # Retrieve user and verify status
        user = await self.user_repo.get_by_id(session.user_id)
        if not user or not user.is_active:
            raise UnauthorizedError("Account is inactive or not found", code="ACCOUNT_INACTIVE")

        # Rotate: Issue new access token + new refresh token in the SAME token family
        new_access_token = create_access_token(user.id, user.role)
        new_raw_refresh = generate_secure_token()
        new_refresh_expires_at = datetime.now(UTC) + timedelta(days=settings.JWT_REFRESH_TOKEN_EXPIRE_DAYS)

        await self.session_repo.create_session(
            user_id=user.id,
            refresh_token_hash=hash_token(new_raw_refresh),
            token_family=session.token_family,
            expires_at=new_refresh_expires_at,
            user_agent=user_agent or session.user_agent,
            ip_address=ip_address or session.ip_address,
        )

        # Audit log token refresh
        await self.audit_repo.log_event(
            action="TOKEN_REFRESHED",
            resource_type="user_session",
            actor_id=str(user.id),
            resource_id=str(session.id),
            status="success",
            ip_address=ip_address,
            request_id=request_id,
        )

        expires_in = settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES * 60
        return user, new_access_token, new_raw_refresh, expires_in

    async def logout(
        self,
        raw_refresh_token: str | None,
        user_id: uuid.UUID | None = None,
        ip_address: str | None = None,
        request_id: str | None = None,
    ) -> None:
        """Revokes the current active session."""
        if raw_refresh_token:
            token_hash = hash_token(raw_refresh_token)
            session = await self.session_repo.get_by_token_hash(token_hash)
            if session and session.revoked_at is None:
                await self.session_repo.revoke_session(session)
                await self.audit_repo.log_event(
                    action="USER_LOGOUT",
                    resource_type="user_session",
                    actor_id=str(session.user_id),
                    resource_id=str(session.id),
                    status="success",
                    ip_address=ip_address,
                    request_id=request_id,
                )

    async def logout_all(
        self,
        user_id: uuid.UUID,
        ip_address: str | None = None,
        request_id: str | None = None,
    ) -> int:
        """Revokes all active sessions for the user across all devices."""
        count = await self.session_repo.revoke_all_user_sessions(user_id)
        await self.audit_repo.log_event(
            action="USER_LOGOUT_ALL",
            resource_type="user",
            actor_id=str(user_id),
            resource_id=str(user_id),
            status="success",
            details={"revoked_sessions_count": count},
            ip_address=ip_address,
            request_id=request_id,
        )
        return count

    async def change_password(
        self,
        user: User,
        current_password: str,
        new_password: str,
        ip_address: str | None = None,
        request_id: str | None = None,
    ) -> None:
        """Verifies existing password, updates hash, and revokes other sessions."""
        if not verify_password(current_password, user.password_hash):
            raise UnauthorizedError("Current password is incorrect", code="INVALID_CURRENT_PASSWORD")

        validate_password_strength(new_password)
        new_hash = hash_password(new_password)

        await self.user_repo.update_password(user, new_hash)
        # Invalidate active sessions on password change for security
        await self.session_repo.revoke_all_user_sessions(user.id)

        await self.audit_repo.log_event(
            action="PASSWORD_CHANGED",
            resource_type="user",
            actor_id=str(user.id),
            resource_id=str(user.id),
            status="success",
            ip_address=ip_address,
            request_id=request_id,
        )

    async def list_user_sessions(
        self,
        user_id: uuid.UUID,
        current_refresh_token: str | None = None,
    ) -> list[dict[str, Any]]:
        """Returns list of active sessions with current session identification."""
        sessions = await self.session_repo.list_active_user_sessions(user_id)
        current_hash = hash_token(current_refresh_token) if current_refresh_token else None

        result: list[dict[str, Any]] = []
        for s in sessions:
            result.append(
                {
                    "id": s.id,
                    "created_at": s.created_at,
                    "expires_at": s.expires_at,
                    "last_used_at": s.last_used_at,
                    "user_agent": s.user_agent,
                    "ip_address": s.ip_address,
                    "is_current": bool(current_hash and s.refresh_token_hash == current_hash),
                }
            )
        return result

    async def revoke_user_session(
        self,
        user_id: uuid.UUID,
        session_id: uuid.UUID,
        ip_address: str | None = None,
        request_id: str | None = None,
    ) -> None:
        """Revokes a specific user session by ID, enforcing ownership."""
        session = await self.session_repo.get_by_id(session_id)
        if not session or session.user_id != user_id:
            raise NotFoundError("Session not found", code="SESSION_NOT_FOUND")

        if session.revoked_at is None:
            await self.session_repo.revoke_session(session)
            await self.audit_repo.log_event(
                action="TOKEN_REVOKED",
                resource_type="user_session",
                actor_id=str(user_id),
                resource_id=str(session.id),
                status="success",
                ip_address=ip_address,
                request_id=request_id,
            )

    async def demo_login(
        self,
        user_agent: str | None = None,
        ip_address: str | None = None,
        request_id: str | None = None,
    ) -> tuple[User, str, str, int]:
        """Development-only login that idempotently creates/retrieves the demo user and issues real session tokens.

        Security boundary: Strictly blocked if DEMO_LOGIN_ENABLED is False or environment is production.
        """
        if not settings.is_demo_login_allowed:
            await self.audit_repo.log_event(
                action="DEMO_LOGIN_BLOCKED",
                resource_type="auth",
                status="failure",
                details={
                    "reason": "demo_login_disabled_or_production",
                    "effective_environment": settings.effective_environment,
                    "demo_enabled": settings.DEMO_LOGIN_ENABLED,
                },
                ip_address=ip_address,
                request_id=request_id,
            )
            raise ForbiddenError("Demo login is disabled.", code="DEMO_LOGIN_DISABLED")

        demo_email = "demo@selfhealingrag.local"
        demo_name = "Jeeva Developer"

        # 1. Idempotently retrieve or create demo user
        user = await self.user_repo.get_by_email(demo_email)
        if not user:
            # Generate a secure random password hash (demo login uses the dedicated route, not plaintext passwords)
            random_secret = generate_secure_token()
            hashed_secret = hash_password(random_secret)
            user = await self.user_repo.create_user(
                email=demo_email,
                name=demo_name,
                password_hash=hashed_secret,
                role=UserRole.USER.value,
                is_active=True,
                is_verified=True,
            )
            await self.audit_repo.log_event(
                action="DEMO_USER_CREATED",
                resource_type="user",
                actor_id=str(user.id),
                resource_id=str(user.id),
                status="success",
                details={"email": demo_email, "role": user.role},
                ip_address=ip_address,
                request_id=request_id,
            )
            logger.info(f"Initialized development demo user: id={user.id} email={demo_email}")

        if not user.is_active:
            raise UnauthorizedError(
                "Demo account is deactivated. Please reset database state.",
                code="ACCOUNT_DEACTIVATED",
            )

        # 2. Update last login timestamp
        await self.user_repo.update_last_login(user)

        # 3. Issue REAL JWT access token and rotated refresh token session
        access_token = create_access_token(user.id, user.role)
        raw_refresh_token = generate_secure_token()
        token_family = str(uuid.uuid4())
        refresh_expires_at = datetime.now(UTC) + timedelta(days=settings.JWT_REFRESH_TOKEN_EXPIRE_DAYS)

        await self.session_repo.create_session(
            user_id=user.id,
            refresh_token_hash=hash_token(raw_refresh_token),
            token_family=token_family,
            expires_at=refresh_expires_at,
            user_agent=user_agent,
            ip_address=ip_address,
        )

        # 4. Audit success
        await self.audit_repo.log_event(
            action="DEMO_LOGIN_SUCCESS",
            resource_type="user",
            actor_id=str(user.id),
            resource_id=str(user.id),
            status="success",
            details={"email": user.email, "role": user.role},
            ip_address=ip_address,
            request_id=request_id,
        )

        expires_in = settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES * 60
        return user, access_token, raw_refresh_token, expires_in
