"""Repository for system audit logging operations."""

from collections.abc import Sequence
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.infrastructure.database.models import AuditLog
from app.repositories.base import BaseRepository


class AuditRepository(BaseRepository[AuditLog]):
    def __init__(self, session: AsyncSession):
        super().__init__(AuditLog, session)

    async def log_event(
        self,
        action: str,
        resource_type: str,
        actor_id: str | None = None,
        resource_id: str | None = None,
        status: str = "success",
        details: dict[str, Any] | None = None,
        ip_address: str | None = None,
        request_id: str | None = None,
    ) -> AuditLog:
        """Creates and persists an audit entry."""
        audit = AuditLog(
            action=action,
            resource_type=resource_type,
            actor_id=actor_id,
            resource_id=resource_id,
            status=status,
            details=details,
            ip_address=ip_address,
            request_id=request_id,
        )
        return await self.create(audit)

    async def get_recent_logs(self, limit: int = 50) -> Sequence[AuditLog]:
        """Returns recent audit events ordered by creation timestamp."""
        stmt = select(AuditLog).order_by(AuditLog.created_at.desc()).limit(limit)
        result = await self.session.execute(stmt)
        return result.scalars().all()
