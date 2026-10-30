"""Repository for Document and DocumentVersion model operations."""

from uuid import UUID

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.infrastructure.database.models import (
    Document,
    DocumentChunk,
    DocumentVersion,
)
from app.repositories.base import BaseRepository


def _as_uuid(val: UUID | str) -> UUID:
    return val if isinstance(val, UUID) else UUID(str(val))


class DocumentRepository(BaseRepository[Document]):
    """Repository managing Document persistence, versions, and checksum queries."""

    def __init__(self, session: AsyncSession):
        super().__init__(Document, session)

    async def get_by_id_and_owner(self, document_id: UUID | str, owner_id: UUID | str) -> Document | None:
        doc_uuid = _as_uuid(document_id)
        owner_uuid = _as_uuid(owner_id)
        stmt = select(Document).where(
            Document.id == doc_uuid,
            Document.owner_id == owner_uuid,
        )
        result = await self.session.execute(stmt)
        return result.scalars().first()

    async def get_by_checksum_and_kb(self, kb_id: UUID | str, checksum: str) -> Document | None:
        """Finds if a document with identical content checksum already exists in the Knowledge Base."""
        kb_uuid = _as_uuid(kb_id)
        stmt = select(Document).where(
            Document.knowledge_base_id == kb_uuid,
            Document.checksum == checksum,
        )
        result = await self.session.execute(stmt)
        return result.scalars().first()

    async def list_by_kb(
        self, kb_id: UUID | str, owner_id: UUID | str, offset: int = 0, limit: int = 50
    ) -> tuple[list[Document], int]:
        kb_uuid = _as_uuid(kb_id)
        owner_uuid = _as_uuid(owner_id)
        total_stmt = select(func.count(Document.id)).where(
            Document.knowledge_base_id == kb_uuid,
            Document.owner_id == owner_uuid,
        )
        total = (await self.session.execute(total_stmt)).scalar_one()

        stmt = (
            select(Document)
            .where(
                Document.knowledge_base_id == kb_uuid,
                Document.owner_id == owner_uuid,
            )
            .order_by(Document.created_at.desc())
            .offset(offset)
            .limit(limit)
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all()), total

    async def get_chunk_count(self, document_id: UUID | str) -> int:
        doc_uuid = _as_uuid(document_id)
        stmt = select(func.count(DocumentChunk.id)).where(DocumentChunk.document_id == doc_uuid)
        return (await self.session.execute(stmt)).scalar_one()

    async def create_version(
        self,
        document_id: UUID | str,
        checksum: str,
        storage_key: str,
        version_number: int = 1,
    ) -> DocumentVersion:
        doc_uuid = _as_uuid(document_id)
        version = DocumentVersion(
            document_id=doc_uuid,
            version_number=version_number,
            checksum=checksum,
            storage_key=storage_key,
            is_active=True,
        )
        self.session.add(version)
        await self.session.flush()
        await self.session.refresh(version)
        return version

    async def get_active_version(self, document_id: UUID | str) -> DocumentVersion | None:
        doc_uuid = _as_uuid(document_id)
        stmt = (
            select(DocumentVersion)
            .where(
                DocumentVersion.document_id == doc_uuid,
                DocumentVersion.is_active == True,  # noqa: E712
            )
            .order_by(DocumentVersion.version_number.desc())
        )
        result = await self.session.execute(stmt)
        return result.scalars().first()

    async def list_versions(self, document_id: UUID | str) -> list[DocumentVersion]:
        """Lists all versions belonging to a document ordered by version_number desc."""
        doc_uuid = _as_uuid(document_id)
        stmt = (
            select(DocumentVersion)
            .where(DocumentVersion.document_id == doc_uuid)
            .order_by(DocumentVersion.version_number.desc())
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def deactivate_versions(self, document_id: UUID | str) -> None:
        """Sets is_active=False on all versions of a document."""
        doc_uuid = _as_uuid(document_id)
        versions = await self.list_versions(doc_uuid)
        for v in versions:
            v.is_active = False
        await self.session.flush()

    async def delete_chunks_for_document(self, document_id: UUID | str) -> int:
        """Deletes all chunks belonging to a document (used during reprocessing or deletion)."""
        doc_uuid = _as_uuid(document_id)
        stmt = delete(DocumentChunk).where(DocumentChunk.document_id == doc_uuid)
        result = await self.session.execute(stmt)
        await self.session.flush()
        return result.rowcount
