"""Repository for KnowledgeBaseRepairJob operations."""

from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.infrastructure.database.models import KnowledgeBaseRepairJob
from app.repositories.base import BaseRepository


def _as_uuid(val: UUID | str) -> UUID:
    return val if isinstance(val, UUID) else UUID(str(val))


class RepairJobRepository(BaseRepository[KnowledgeBaseRepairJob]):
    """Repository managing persistence and queries for knowledge base repair jobs."""

    def __init__(self, session: AsyncSession):
        super().__init__(KnowledgeBaseRepairJob, session)

    async def get_by_id_and_owner(self, job_id: UUID | str, user_id: UUID | str) -> KnowledgeBaseRepairJob | None:
        """Retrieves a specific repair job ensuring user ownership."""
        j_uuid = _as_uuid(job_id)
        u_uuid = _as_uuid(user_id)
        stmt = select(KnowledgeBaseRepairJob).where(
            KnowledgeBaseRepairJob.id == j_uuid,
            KnowledgeBaseRepairJob.user_id == u_uuid,
        )
        res = await self.session.execute(stmt)
        return res.scalars().first()

    async def get_active_job_for_document(self, document_id: UUID | str) -> KnowledgeBaseRepairJob | None:
        """Returns active repair job running on a document to prevent concurrent races."""
        d_uuid = _as_uuid(document_id)
        stmt = select(KnowledgeBaseRepairJob).where(
            KnowledgeBaseRepairJob.document_id == d_uuid,
            KnowledgeBaseRepairJob.status.in_(["PENDING", "RUNNING"]),
        )
        res = await self.session.execute(stmt)
        return res.scalars().first()

    async def list_by_kb(
        self,
        kb_id: UUID | str,
        user_id: UUID | str,
        offset: int = 0,
        limit: int = 50,
    ) -> tuple[list[KnowledgeBaseRepairJob], int]:
        """Lists repair jobs for a knowledge base with pagination."""
        kb_uuid = _as_uuid(kb_id)
        u_uuid = _as_uuid(user_id)

        total_stmt = select(func.count(KnowledgeBaseRepairJob.id)).where(
            KnowledgeBaseRepairJob.knowledge_base_id == kb_uuid,
            KnowledgeBaseRepairJob.user_id == u_uuid,
        )
        total = (await self.session.execute(total_stmt)).scalar_one()

        stmt = (
            select(KnowledgeBaseRepairJob)
            .where(
                KnowledgeBaseRepairJob.knowledge_base_id == kb_uuid,
                KnowledgeBaseRepairJob.user_id == u_uuid,
            )
            .order_by(KnowledgeBaseRepairJob.created_at.desc())
            .offset(offset)
            .limit(limit)
        )
        res = await self.session.execute(stmt)
        return list(res.scalars().all()), total
