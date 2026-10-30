"""Knowledge Base Versioning Engine: manages document version lineage, freshness, and safe zero-downtime reindexing."""

import hashlib
import math
from uuid import UUID, uuid4

from app.core.config import settings
from app.core.exceptions import AppError
from app.core.logging import get_logger
from app.domain.interfaces.embeddings import EmbeddingProviderInterface
from app.domain.interfaces.storage import ObjectStorageInterface
from app.infrastructure.database.models import (
    DocumentChunk,
    DocumentStatus,
    DocumentVersion,
)
from app.infrastructure.embedding.factory import get_embedding_provider
from app.infrastructure.storage.local_storage import LocalStorageProvider
from app.repositories.chunk_repository import ChunkRepository
from app.repositories.document_repository import DocumentRepository
from app.schemas.knowledge_base import (
    DocumentVersionHistoryResponse,
    DocumentVersionItem,
)
from app.services.chunker import DocumentChunker
from app.services.normalizer import TextNormalizer
from app.services.parsers.factory import ParserFactory
from sqlalchemy.ext.asyncio import AsyncSession

logger = get_logger("app.services.kb.versioning")


class KnowledgeBaseVersioningEngine:
    """Safely manages version lineage, freshness tracking, and non-destructive re-indexing."""

    def __init__(
        self,
        session: AsyncSession,
        storage_provider: ObjectStorageInterface | None = None,
        embedding_provider: EmbeddingProviderInterface | None = None,
    ):
        self.session = session
        self.doc_repo = DocumentRepository(session)
        self.chunk_repo = ChunkRepository(session)
        self.storage = storage_provider or LocalStorageProvider()
        self.embeddings = embedding_provider or get_embedding_provider()
        self.chunker = DocumentChunker(
            chunk_size=settings.CHUNK_SIZE,
            chunk_overlap=settings.CHUNK_OVERLAP,
        )

    async def get_version_history(
        self,
        document_id: UUID,
        user_id: UUID,
    ) -> DocumentVersionHistoryResponse:
        """Retrieves complete version history and chunk counts for a document."""
        doc = await self.doc_repo.get_by_id_and_owner(document_id, user_id)
        if not doc:
            raise AppError(
                code="DOCUMENT_NOT_FOUND",
                message="Document not found or access denied.",
                status_code=404,
            )

        versions = await self.doc_repo.list_versions(doc.id)
        active_ver_num = 1
        version_items: list[DocumentVersionItem] = []

        for v in versions:
            count = await self.chunk_repo.count_by_version(v.id)
            if v.is_active:
                active_ver_num = v.version_number
            version_items.append(
                DocumentVersionItem(
                    id=v.id,
                    document_id=v.document_id,
                    version_number=v.version_number,
                    checksum=v.checksum,
                    storage_key=v.storage_key,
                    is_active=v.is_active,
                    chunk_count=count,
                    created_at=v.created_at,
                )
            )

        return DocumentVersionHistoryResponse(
            document_id=doc.id,
            filename=doc.filename,
            active_version_number=active_ver_num,
            total_versions=len(version_items),
            is_fresh=True,
            versions=version_items,
        )

    async def reindex_document(
        self,
        document_id: UUID,
        user_id: UUID,
        new_file_bytes: bytes | None = None,
    ) -> tuple[DocumentVersion, int]:
        """Safely reindexes a document by staging version N+1.

        Preserves the current active version until the new version is fully
        parsed, chunked, embedded, and verified.
        """
        doc = await self.doc_repo.get_by_id_and_owner(document_id, user_id)
        if not doc:
            raise AppError(
                code="DOCUMENT_NOT_FOUND",
                message="Document not found or access denied.",
                status_code=404,
            )

        active_version = await self.doc_repo.get_active_version(doc.id)
        existing_versions = await self.doc_repo.list_versions(doc.id)
        max_ver = max([v.version_number for v in existing_versions], default=0)
        next_ver_num = max_ver + 1

        # 1. Determine source bytes and storage
        if new_file_bytes is not None:
            file_bytes = new_file_bytes
            checksum = hashlib.sha256(file_bytes).hexdigest()
            storage_key = f"kbs/{doc.knowledge_base_id}/{doc.id}/v{next_ver_num}_{doc.filename}"
            await self.storage.save(file_bytes, storage_key, doc.content_type)
        else:
            # Use current storage key
            storage_key = active_version.storage_key if active_version else doc.storage_key
            file_bytes = await self.storage.load(storage_key)
            checksum = active_version.checksum if active_version else doc.checksum

        # 2. Stage new inactive version
        staged_version = DocumentVersion(
            id=uuid4(),
            document_id=doc.id,
            version_number=next_ver_num,
            checksum=checksum,
            storage_key=storage_key,
            is_active=False,  # Inactive until verified
        )
        self.session.add(staged_version)
        await self.session.flush()

        try:
            # 3. Parse and chunk
            parser = ParserFactory.get_parser(doc.filename, doc.content_type)
            parsed_doc = parser.parse(file_bytes, doc.filename)

            if parsed_doc.is_scanned:
                raise AppError(
                    code="OCR_REQUIRED",
                    message="Document requires OCR for text extraction.",
                    status_code=422,
                )
            if parsed_doc.error:
                raise AppError(
                    code="PARSING_FAILED",
                    message=f"Parser failed: {parsed_doc.error}",
                    status_code=422,
                )

            for unit in parsed_doc.units:
                unit.text = TextNormalizer.normalize(unit.text)

            chunks_data = self.chunker.chunk_document(
                parsed_doc=parsed_doc,
                document_id=str(doc.id),
                document_version_id=str(staged_version.id),
                source_filename=doc.original_filename,
            )

            if not chunks_data:
                raise AppError(
                    code="NO_CHUNKS_GENERATED",
                    message="No extractable text or usable chunks produced.",
                    status_code=422,
                )

            # 4. Generate & Validate Embeddings
            texts_to_embed = [c.content for c in chunks_data]
            vectors = await self.embeddings.embed_documents(texts_to_embed)

            if len(vectors) != len(chunks_data):
                raise AppError(
                    code="EMBEDDING_COUNT_MISMATCH",
                    message=f"Generated {len(vectors)} vectors for {len(chunks_data)} chunks.",
                    status_code=502,
                )

            dim = self.embeddings.dimension
            for i, vec in enumerate(vectors):
                if vec is None or len(vec) != dim:
                    raise AppError(
                        code="EMBEDDING_DIM_MISMATCH",
                        message=f"Chunk {i} embedding dimension mismatch: expected {dim}.",
                        status_code=502,
                    )
                if any(not math.isfinite(x) for x in vec):
                    raise AppError(
                        code="INVALID_EMBEDDING_VALUES",
                        message=f"Chunk {i} embedding contains non-finite or NaN values.",
                        status_code=502,
                    )

            # 5. Build Chunk Entities
            chunk_entities: list[DocumentChunk] = []
            for i, chunk_res in enumerate(chunks_data):
                meta = {
                    **chunk_res.metadata,
                    "embedding_model": self.embeddings.model_name,
                    "embedding_provider": self.embeddings.provider_name,
                    "embedding_dimension": dim,
                }
                chunk_entities.append(
                    DocumentChunk(
                        document_id=doc.id,
                        document_version_id=staged_version.id,
                        chunk_index=chunk_res.chunk_index,
                        content=chunk_res.content,
                        token_count=chunk_res.token_count,
                        character_count=chunk_res.character_count,
                        page_number=chunk_res.page_number,
                        section_title=chunk_res.section_title,
                        start_offset=chunk_res.start_offset,
                        end_offset=chunk_res.end_offset,
                        chunk_metadata=meta,
                        embedding=vectors[i],
                    )
                )

            # Persist staged chunks
            await self.chunk_repo.create_chunks(chunk_entities)

            # 6. Atomic Promotion
            # Deactivate previous active versions
            for v in existing_versions:
                v.is_active = False
                # Remove prior chunks now that replacement is verified
                await self.chunk_repo.delete_by_version(v.id)

            staged_version.is_active = True
            doc.checksum = checksum
            doc.storage_key = storage_key
            doc.file_size = len(file_bytes)
            doc.status = DocumentStatus.READY
            doc.ingestion_error = None

            await self.session.commit()
            await self.session.refresh(staged_version)
            logger.info(
                "DOCUMENT_REINDEXED_SUCCESSFULLY: doc_id=%s version=%d chunks=%d",
                doc.id,
                staged_version.version_number,
                len(chunk_entities),
            )
            return staged_version, len(chunk_entities)

        except Exception as exc:
            # Revert staged version and any staged chunks, preserving previous active state!
            logger.error(
                "DOCUMENT_REINDEXING_FAILED: doc_id=%s staged_ver=%d error=%s",
                doc.id,
                staged_version.version_number,
                str(exc),
            )
            await self.session.rollback()

            # Ensure previous active state is clean in DB
            clean_session_doc = await self.doc_repo.get_by_id(doc.id)
            if clean_session_doc and active_version:
                # If document had a prior active version with chunks, keep it READY
                prior_chunks = await self.doc_repo.get_chunk_count(doc.id)
                if prior_chunks > 0:
                    clean_session_doc.status = DocumentStatus.READY
                    clean_session_doc.ingestion_error = None
                    await self.session.commit()

            raise
