"""Session and refresh token repository for managing active credentials and token rotations."""

import uuid
from collections.abc import Sequence
from datetime import UTC, datetime

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.infrastructure.database.models import UserSession
from app.repositories.base import BaseRepository


class SessionRepository(BaseRepository[UserSession]):
    """Repository handling database operations for UserSession records."""

    def __init__(self, session: AsyncSession):
        super().__init__(UserSession, session)

    async def create_session(
        self,
        user_id: uuid.UUID,
        refresh_token_hash: str,
        token_family: str,
        expires_at: datetime,
        user_agent: str | None = None,
        ip_address: str | None = None,
    ) -> UserSession:
        """Stores a new session record with hashed token credential."""
        new_session = UserSession(
            user_id=user_id,
            refresh_token_hash=refresh_token_hash,
            token_family=token_family,
            expires_at=expires_at,
            last_used_at=datetime.now(UTC),
            user_agent=user_agent[:255] if user_agent else None,
            ip_address=ip_address[:45] if ip_address else None,
        )
        return await self.create(new_session)

    async def get_by_token_hash(self, token_hash: str) -> UserSession | None:
        """Retrieves session by token hash, regardless of revoked status."""
        stmt = select(UserSession).where(UserSession.refresh_token_hash == token_hash)
        result = await self.session.execute(stmt)
        return result.scalars().first()

    async def get_active_by_token_hash(self, token_hash: str) -> UserSession | None:
        """Retrieves non-revoked and unexpired session by token hash."""
        now = datetime.now(UTC)
        stmt = select(UserSession).where(
            UserSession.refresh_token_hash == token_hash,
            UserSession.revoked_at.is_(None),
            UserSession.expires_at > now,
        )
        result = await self.session.execute(stmt)
        return result.scalars().first()

    async def revoke_session(self, session: UserSession) -> None:
        """Revokes an individual session."""
        session.revoked_at = datetime.now(UTC)
        self.session.add(session)
        await self.session.flush()

    async def revoke_token_family(self, token_family: str) -> int:
        """Revokes all sessions in a token family (triggered upon token reuse detection)."""
        now = datetime.now(UTC)
        stmt = (
            update(UserSession)
            .where(
                UserSession.token_family == token_family,
                UserSession.revoked_at.is_(None),
            )
            .values(revoked_at=now)
        )
        result = await self.session.execute(stmt)
        await self.session.flush()
        return result.rowcount or 0

    async def revoke_all_user_sessions(self, user_id: uuid.UUID) -> int:
        """Revokes all active sessions for a given user (logout everywhere)."""
        now = datetime.now(UTC)
        stmt = (
            update(UserSession)
            .where(
                UserSession.user_id == user_id,
                UserSession.revoked_at.is_(None),
            )
            .values(revoked_at=now)
        )
        result = await self.session.execute(stmt)
        await self.session.flush()
        return result.rowcount or 0

    async def list_active_user_sessions(self, user_id: uuid.UUID) -> Sequence[UserSession]:
        """Lists all active and non-revoked sessions for a user."""
        now = datetime.now(UTC)
        stmt = (
            select(UserSession)
            .where(
                UserSession.user_id == user_id,
                UserSession.revoked_at.is_(None),
                UserSession.expires_at > now,
            )
            .order_by(UserSession.created_at.desc())
        )
        result = await self.session.execute(stmt)
        return result.scalars().all()
