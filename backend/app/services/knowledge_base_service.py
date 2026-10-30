"""Service handling Knowledge Base lifecycle, authorization, and cascading cleanup."""

from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import AppError
from app.core.logging import get_logger
from app.domain.interfaces.storage import ObjectStorageInterface
from app.infrastructure.database.models import KnowledgeBase, KnowledgeBaseStatus
from app.infrastructure.storage.local_storage import LocalStorageProvider
from app.repositories.document_repository import DocumentRepository
from app.repositories.knowledge_base_repository import KnowledgeBaseRepository
from app.schemas.knowledge_base import (
    KnowledgeBaseCreate,
    KnowledgeBaseListResponse,
    KnowledgeBaseResponse,
    KnowledgeBaseUpdate,
)

logger = get_logger(__name__)


class KnowledgeBaseService:
    """Manages knowledge bases, enforcing strict user ownership."""

    def __init__(
        self,
        session: AsyncSession,
        storage_provider: ObjectStorageInterface | None = None,
    ):
        self.session = session
        self.kb_repo = KnowledgeBaseRepository(session)
        self.doc_repo = DocumentRepository(session)
        self.storage = storage_provider or LocalStorageProvider()

    async def create_knowledge_base(self, user_id: UUID, data: KnowledgeBaseCreate) -> KnowledgeBaseResponse:
        """Creates a new Knowledge Base owned by user_id."""
        kb = KnowledgeBase(
            owner_id=user_id,
            name=data.name.strip(),
            description=data.description.strip() if data.description else None,
            status=KnowledgeBaseStatus.ACTIVE,
        )
        created = await self.kb_repo.create(kb)
        logger.info("Knowledge Base created: id=%s owner_id=%s name=%s", created.id, user_id, created.name)
        return KnowledgeBaseResponse(
            id=created.id,
            owner_id=created.owner_id,
            name=created.name,
            description=created.description,
            status=created.status,
            created_at=created.created_at,
            updated_at=created.updated_at,
            document_count=0,
            total_chunks=0,
        )

    async def get_knowledge_base(self, kb_id: UUID, user_id: UUID) -> KnowledgeBaseResponse:
        """Retrieves a single Knowledge Base ensuring user ownership."""
        kb = await self.kb_repo.get_by_id_and_owner(kb_id, user_id)
        if not kb:
            raise AppError(
                code="KNOWLEDGE_BASE_NOT_FOUND",
                message="Knowledge base not found or access denied.",
                status_code=404,
            )

        doc_count, chunk_count = await self.kb_repo.get_counts(kb.id)
        return KnowledgeBaseResponse(
            id=kb.id,
            owner_id=kb.owner_id,
            name=kb.name,
            description=kb.description,
            status=kb.status,
            created_at=kb.created_at,
            updated_at=kb.updated_at,
            document_count=doc_count,
            total_chunks=chunk_count,
        )

    async def list_knowledge_bases(self, user_id: UUID, offset: int = 0, limit: int = 50) -> KnowledgeBaseListResponse:
        """Lists all Knowledge Bases owned by user_id with pagination."""
        items, total = await self.kb_repo.list_by_owner(user_id, offset=offset, limit=limit)
        response_items: list[KnowledgeBaseResponse] = []

        for kb in items:
            doc_count, chunk_count = await self.kb_repo.get_counts(kb.id)
            response_items.append(
                KnowledgeBaseResponse(
                    id=kb.id,
                    owner_id=kb.owner_id,
                    name=kb.name,
                    description=kb.description,
                    status=kb.status,
                    created_at=kb.created_at,
                    updated_at=kb.updated_at,
                    document_count=doc_count,
                    total_chunks=chunk_count,
                )
            )

        return KnowledgeBaseListResponse(
            items=response_items,
            total=total,
            limit=limit,
            offset=offset,
        )

    async def update_knowledge_base(
        self, kb_id: UUID, user_id: UUID, data: KnowledgeBaseUpdate
    ) -> KnowledgeBaseResponse:
        """Updates Knowledge Base metadata."""
        kb = await self.kb_repo.get_by_id_and_owner(kb_id, user_id)
        if not kb:
            raise AppError(
                code="KNOWLEDGE_BASE_NOT_FOUND",
                message="Knowledge base not found or access denied.",
                status_code=404,
            )

        if data.name is not None:
            kb.name = data.name.strip()
        if data.description is not None:
            kb.description = data.description.strip()
        if data.status is not None:
            kb.status = data.status

        await self.session.flush()
        await self.session.refresh(kb)

        doc_count, chunk_count = await self.kb_repo.get_counts(kb.id)
        logger.info("Knowledge Base updated: id=%s name=%s", kb.id, kb.name)
        return KnowledgeBaseResponse(
            id=kb.id,
            owner_id=kb.owner_id,
            name=kb.name,
            description=kb.description,
            status=kb.status,
            created_at=kb.created_at,
            updated_at=kb.updated_at,
            document_count=doc_count,
            total_chunks=chunk_count,
        )

    async def delete_knowledge_base(self, kb_id: UUID, user_id: UUID) -> None:
        """Safely cascades deletion across storage files, chunks, versions, and documents."""
        kb = await self.kb_repo.get_by_id_and_owner(kb_id, user_id)
        if not kb:
            raise AppError(
                code="KNOWLEDGE_BASE_NOT_FOUND",
                message="Knowledge base not found or access denied.",
                status_code=404,
            )

        # 1. Fetch all documents in this knowledge base
        docs, _ = await self.doc_repo.list_by_kb(kb.id, user_id, offset=0, limit=10000)

        # 2. Delete physical storage files
        for doc in docs:
            if doc.storage_key:
                try:
                    await self.storage.delete(doc.storage_key)
                except Exception as e:
                    logger.warning("Could not delete file %s from storage: %s", doc.storage_key, e)

        # 3. Database cascade removes documents, versions, chunks, and KB
        await self.kb_repo.delete(kb)
        await self.session.flush()
        await self.session.commit()
        logger.info("Knowledge Base deleted: id=%s with %d documents", kb_id, len(docs))
