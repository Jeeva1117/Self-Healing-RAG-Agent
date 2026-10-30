"""Repository for KnowledgeBase model operations."""

from uuid import UUID

from app.infrastructure.database.models import Document, DocumentChunk, KnowledgeBase
from app.repositories.base import BaseRepository
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession


def _as_uuid(val: UUID | str) -> UUID:
    return val if isinstance(val, UUID) else UUID(str(val))


class KnowledgeBaseRepository(BaseRepository[KnowledgeBase]):
    """Repository managing Knowledge Base entities and relational ownership."""

    def __init__(self, session: AsyncSession):
        super().__init__(KnowledgeBase, session)

    async def get_by_id_and_owner(self, kb_id: UUID | str, owner_id: UUID | str) -> KnowledgeBase | None:
        kb_uuid = _as_uuid(kb_id)
        owner_uuid = _as_uuid(owner_id)
        stmt = select(KnowledgeBase).where(
            KnowledgeBase.id == kb_uuid,
            KnowledgeBase.owner_id == owner_uuid,
        )
        result = await self.session.execute(stmt)
        return result.scalars().first()

    async def list_by_owner(
        self, owner_id: UUID | str, offset: int = 0, limit: int = 50
    ) -> tuple[list[KnowledgeBase], int]:
        owner_uuid = _as_uuid(owner_id)
        total_stmt = select(func.count(KnowledgeBase.id)).where(KnowledgeBase.owner_id == owner_uuid)
        total_result = await self.session.execute(total_stmt)
        total = total_result.scalar_one()

        stmt = (
            select(KnowledgeBase)
            .where(KnowledgeBase.owner_id == owner_uuid)
            .order_by(KnowledgeBase.created_at.desc())
            .offset(offset)
            .limit(limit)
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all()), total

    async def get_counts(self, kb_id: UUID | str) -> tuple[int, int]:
        """Returns (document_count, total_chunks) for the given Knowledge Base."""
        kb_uuid = _as_uuid(kb_id)
        doc_stmt = select(func.count(Document.id)).where(Document.knowledge_base_id == kb_uuid)
        doc_count = (await self.session.execute(doc_stmt)).scalar_one()

        chunk_stmt = (
            select(func.count(DocumentChunk.id))
            .join(Document, Document.id == DocumentChunk.document_id)
            .where(Document.knowledge_base_id == kb_uuid)
        )
        chunk_count = (await self.session.execute(chunk_stmt)).scalar_one()

        return doc_count, chunk_count
