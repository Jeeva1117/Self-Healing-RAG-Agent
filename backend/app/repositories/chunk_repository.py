"""Repository for DocumentChunk queries and persistence."""

from uuid import UUID

from app.infrastructure.database.models import DocumentChunk
from app.repositories.base import BaseRepository
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession


def _as_uuid(val: UUID | str) -> UUID:
    return val if isinstance(val, UUID) else UUID(str(val))


class ChunkRepository(BaseRepository[DocumentChunk]):
    """Repository managing document chunks and vector persistence."""

    def __init__(self, session: AsyncSession):
        super().__init__(DocumentChunk, session)

    async def create_chunks(self, chunks: list[DocumentChunk]) -> list[DocumentChunk]:
        """Batch inserts document chunks."""
        self.session.add_all(chunks)
        await self.session.flush()
        return chunks

    async def delete_by_document(self, document_id: UUID | str) -> int:
        """Deletes all chunks belonging to a document."""
        doc_uuid = _as_uuid(document_id)
        stmt = delete(DocumentChunk).where(DocumentChunk.document_id == doc_uuid)
        res = await self.session.execute(stmt)
        await self.session.flush()
        return res.rowcount or 0

    async def delete_by_version(self, version_id: UUID | str) -> int:
        """Deletes all chunks belonging to a specific version."""
        ver_uuid = _as_uuid(version_id)
        stmt = delete(DocumentChunk).where(DocumentChunk.document_version_id == ver_uuid)
        res = await self.session.execute(stmt)
        await self.session.flush()
        return res.rowcount or 0

    async def count_by_version(self, version_id: UUID | str) -> int:
        """Counts chunks associated with a specific version."""
        ver_uuid = _as_uuid(version_id)
        stmt = select(func.count(DocumentChunk.id)).where(DocumentChunk.document_version_id == ver_uuid)
        res = await self.session.execute(stmt)
        return res.scalar_one() or 0

    async def list_by_document(
        self, document_id: UUID | str, offset: int = 0, limit: int = 50
    ) -> tuple[list[DocumentChunk], int]:
        doc_uuid = _as_uuid(document_id)
        total_stmt = select(func.count(DocumentChunk.id)).where(DocumentChunk.document_id == doc_uuid)
        total = (await self.session.execute(total_stmt)).scalar_one()

        stmt = (
            select(DocumentChunk)
            .where(DocumentChunk.document_id == doc_uuid)
            .order_by(DocumentChunk.chunk_index.asc())
            .offset(offset)
            .limit(limit)
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all()), total
