"""Service managing document ingestion pipeline, parsers, chunking, and pgvector embeddings."""

import hashlib
import math
import os
import re
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.exceptions import AppError
from app.core.logging import get_logger
from app.domain.interfaces.embeddings import EmbeddingProviderInterface
from app.domain.interfaces.storage import ObjectStorageInterface
from app.infrastructure.database.models import (
    Document,
    DocumentChunk,
    DocumentStatus,
)
from app.infrastructure.embedding.factory import get_embedding_provider
from app.infrastructure.storage.local_storage import LocalStorageProvider
from app.repositories.chunk_repository import ChunkRepository
from app.repositories.document_repository import DocumentRepository
from app.repositories.knowledge_base_repository import KnowledgeBaseRepository
from app.schemas.document import DocumentChunkResponse, DocumentResponse
from app.services.chunker import DocumentChunker
from app.services.normalizer import TextNormalizer
from app.services.parsers.base import ParsedDocument
from app.services.parsers.factory import ParserFactory

logger = get_logger(__name__)


class IngestionService:
    """Orchestrates document upload, validation, parsing, normalization, chunking, and embedding."""

    def __init__(
        self,
        session: AsyncSession,
        storage_provider: ObjectStorageInterface | None = None,
        embedding_provider: EmbeddingProviderInterface | None = None,
    ):
        self.session = session
        self.doc_repo = DocumentRepository(session)
        self.kb_repo = KnowledgeBaseRepository(session)
        self.chunk_repo = ChunkRepository(session)
        self.storage = storage_provider or LocalStorageProvider()
        self.embeddings = embedding_provider or get_embedding_provider()
        self.chunker = DocumentChunker(
            chunk_size=settings.CHUNK_SIZE,
            chunk_overlap=settings.CHUNK_OVERLAP,
        )

    @staticmethod
    def sanitize_filename(filename: str) -> str:
        """Sanitizes filename against path traversal and dangerous characters."""
        base_name = os.path.basename(filename)
        clean_name = re.sub(r"[^\w\s\.-]", "_", base_name).strip()
        return clean_name or "uploaded_document"

    async def validate_and_create_document(
        self,
        kb_id: UUID,
        user_id: UUID,
        filename: str,
        content_type: str,
        file_bytes: bytes,
        document_metadata: dict[str, Any] | None = None,
    ) -> Document:
        """Validates upload constraints, detects duplicates, stores file, and persists initial record."""
        # 1. Verify Knowledge Base exists and is owned by user
        kb = await self.kb_repo.get_by_id_and_owner(kb_id, user_id)
        if not kb:
            raise AppError(
                code="KNOWLEDGE_BASE_NOT_FOUND",
                message="Knowledge base not found or access denied.",
                status_code=404,
            )

        # 2. Validate file size
        max_bytes = settings.MAX_UPLOAD_SIZE_MB * 1024 * 1024
        file_size = len(file_bytes)
        if file_size == 0:
            raise AppError(
                code="EMPTY_FILE",
                message="Uploaded file is empty (0 bytes).",
                status_code=400,
            )
        if file_size > max_bytes:
            mb_size = file_size / (1024 * 1024)
            raise AppError(
                code="FILE_TOO_LARGE",
                message=f"File size ({mb_size:.2f}MB) exceeds configured limit of {settings.MAX_UPLOAD_SIZE_MB}MB.",
                status_code=413,
            )

        # 3. Validate file extension
        sanitized_name = self.sanitize_filename(filename)
        ext = sanitized_name.split(".")[-1].lower() if "." in sanitized_name else ""
        if ext not in settings.ALLOWED_DOCUMENT_TYPES:
            allowed_str = ", ".join(settings.ALLOWED_DOCUMENT_TYPES)
            raise AppError(
                code="UNSUPPORTED_DOCUMENT_FORMAT",
                message=f"File extension '.{ext}' is not supported. Allowed formats: {allowed_str}",
                status_code=400,
            )

        # 4. Calculate SHA-256 Checksum
        checksum = hashlib.sha256(file_bytes).hexdigest()

        # 5. Duplicate Detection within same Knowledge Base
        existing = await self.doc_repo.get_by_checksum_and_kb(kb_id, checksum)
        if existing and existing.status != DocumentStatus.DELETED:
            raise AppError(
                code="DUPLICATE_DOCUMENT",
                message=(
                    f"A document with identical content has already been uploaded to this Knowledge Base "
                    f"(Existing file: '{existing.original_filename}')."
                ),
                status_code=409,
            )

        # 6. Store file safely in storage provider
        doc_id = uuid4()
        storage_key = f"kbs/{kb_id}/{doc_id}/{sanitized_name}"
        await self.storage.save(file_bytes, storage_key, content_type)

        try:
            # 7. Create Document record
            doc = Document(
                id=doc_id,
                knowledge_base_id=kb_id,
                owner_id=user_id,
                filename=sanitized_name,
                original_filename=filename,
                content_type=content_type,
                file_size=file_size,
                checksum=checksum,
                storage_key=storage_key,
                status=DocumentStatus.UPLOADED,
                document_metadata=document_metadata or {},
            )
            created_doc = await self.doc_repo.create(doc)

            # 8. Create Version 1 record
            await self.doc_repo.create_version(
                document_id=doc_id,
                checksum=checksum,
                storage_key=storage_key,
                version_number=1,
            )
        except Exception:
            try:
                await self.storage.delete(storage_key)
            except Exception as del_err:
                logger.warning("Failed to clean up storage key %s after DB error: %s", storage_key, del_err)
            raise

        logger.info(
            "DOCUMENT_UPLOAD_STARTED: id=%s kb_id=%s filename=%s size=%d",
            doc_id,
            kb_id,
            sanitized_name,
            file_size,
        )
        return created_doc

    async def run_ingestion_pipeline(self, document_id: UUID | str) -> None:
        """Executes full document ingestion: Parse -> Normalize -> Chunk -> Embed -> Persist."""
        doc_uuid = document_id if isinstance(document_id, UUID) else UUID(str(document_id))
        doc = await self.doc_repo.get_by_id(doc_uuid)
        if not doc:
            logger.error("Ingestion failed: Document %s not found", doc_uuid)
            return

        try:
            # Set status to PROCESSING and commit so observers immediately see active progress
            doc.status = DocumentStatus.PROCESSING
            doc.ingestion_error = None
            await self.session.commit()

            logger.info("DOCUMENT_PARSING_STARTED: doc_id=%s filename=%s", doc.id, doc.filename)

            # 1. Fetch file bytes from storage
            file_bytes = await self.storage.load(doc.storage_key)

            # 2. Select parser and parse
            parser = ParserFactory.get_parser(doc.filename, doc.content_type)
            parsed_doc: ParsedDocument = parser.parse(file_bytes, doc.filename)

            if parsed_doc.is_scanned:
                doc.status = DocumentStatus.OCR_REQUIRED
                doc.ingestion_error = (
                    parsed_doc.error
                    or "UNSUPPORTED_SCANNED_DOCUMENT: Scanned image with no extractable text. OCR required."
                )
                await self.session.commit()
                logger.warning("DOCUMENT_INGESTION_OCR_REQUIRED: doc_id=%s error=%s", doc.id, doc.ingestion_error)
                return

            if parsed_doc.error:
                doc.status = DocumentStatus.FAILED
                doc.ingestion_error = parsed_doc.error
                await self.session.commit()
                logger.warning("DOCUMENT_INGESTION_FAILED: doc_id=%s error=%s", doc.id, doc.ingestion_error)
                return

            # 3. Normalize parsed units
            for unit in parsed_doc.units:
                unit.text = TextNormalizer.normalize(unit.text)

            # 4. Intelligent structure-aware chunking
            active_version = await self.doc_repo.get_active_version(doc.id)
            version_id = str(active_version.id) if active_version else None

            chunks_data = self.chunker.chunk_document(
                parsed_doc=parsed_doc,
                document_id=str(doc.id),
                document_version_id=version_id,
                source_filename=doc.original_filename,
            )

            if not chunks_data:
                doc.status = DocumentStatus.FAILED
                doc.ingestion_error = "NO_CHUNKS_GENERATED: Document contains zero extractable text or usable chunks."
                await self.session.commit()
                logger.warning("DOCUMENT_INGESTION_FAILED: doc_id=%s no usable chunks", doc.id)
                return

            logger.info(
                "DOCUMENT_CHUNKING_COMPLETED: doc_id=%s chunk_count=%d",
                doc.id,
                len(chunks_data),
            )

            # 5. Generate Embeddings in batches
            logger.info(
                "DOCUMENT_EMBEDDING_STARTED: doc_id=%s count=%d model=%s",
                doc.id,
                len(chunks_data),
                self.embeddings.model_name,
            )
            texts_to_embed = [c.content for c in chunks_data]
            vectors = await self.embeddings.embed_documents(texts_to_embed)

            # Strict Ingestion Quality Validation: check vector count, dimensions, and finite values
            if len(vectors) != len(chunks_data):
                doc.status = DocumentStatus.FAILED
                doc.ingestion_error = (
                    f"EMBEDDING_COUNT_MISMATCH: Provider returned {len(vectors)} embeddings "
                    f"for {len(chunks_data)} chunks."
                )
                await self.session.commit()
                logger.error("DOCUMENT_INGESTION_FAILED: doc_id=%s %s", doc.id, doc.ingestion_error)
                return

            dim = self.embeddings.dimension
            for idx, vec in enumerate(vectors):
                if vec is None or len(vec) != dim:
                    doc.status = DocumentStatus.FAILED
                    doc.ingestion_error = (
                        f"EMBEDDING_DIM_MISMATCH: Chunk {idx} vector dimension mismatch "
                        f"(expected {dim}, got {len(vec) if vec else 0})."
                    )
                    await self.session.commit()
                    logger.error("DOCUMENT_INGESTION_FAILED: doc_id=%s %s", doc.id, doc.ingestion_error)
                    return

                if any(not math.isfinite(x) for x in vec):
                    doc.status = DocumentStatus.FAILED
                    doc.ingestion_error = (
                        f"INVALID_EMBEDDING_VALUES: Chunk {idx} vector contains non-finite or NaN values."
                    )
                    await self.session.commit()
                    logger.error("DOCUMENT_INGESTION_FAILED: doc_id=%s %s", doc.id, doc.ingestion_error)
                    return

            # 6. Build chunk database entities
            chunk_entities: list[DocumentChunk] = []
            for i, chunk_res in enumerate(chunks_data):
                vec = vectors[i]
                # Augment metadata with embedding model info
                meta = {
                    **chunk_res.metadata,
                    **(doc.document_metadata or {}),
                    "embedding_model": self.embeddings.model_name,
                    "embedding_provider": self.embeddings.provider_name,
                    "embedding_dimension": self.embeddings.dimension,
                }

                entity = DocumentChunk(
                    document_id=doc.id,
                    document_version_id=active_version.id if active_version else None,
                    chunk_index=chunk_res.chunk_index,
                    content=chunk_res.content,
                    token_count=chunk_res.token_count,
                    character_count=chunk_res.character_count,
                    page_number=chunk_res.page_number,
                    section_title=chunk_res.section_title,
                    start_offset=chunk_res.start_offset,
                    end_offset=chunk_res.end_offset,
                    chunk_metadata=meta,
                    embedding=vec,
                )
                chunk_entities.append(entity)

            # Persist chunks (replacing any prior chunks for document)
            await self.chunk_repo.delete_by_document(doc.id)
            await self.chunk_repo.create_chunks(chunk_entities)

            # 7. Update Document status to READY
            doc.status = DocumentStatus.READY
            doc.ingestion_error = None
            await self.session.commit()

            logger.info(
                "DOCUMENT_INGESTION_COMPLETED: doc_id=%s chunks=%d embedding_dim=%d",
                doc.id,
                len(chunk_entities),
                self.embeddings.dimension,
            )

        except Exception as e:
            logger.error("DOCUMENT_INGESTION_FAILED: doc_id=%s error=%s", doc_uuid, str(e), exc_info=True)
            await self.session.rollback()
            try:
                failed_doc = await self.doc_repo.get_by_id(doc_uuid)
                if failed_doc:
                    failed_doc.status = DocumentStatus.FAILED
                    failed_doc.ingestion_error = f"Ingestion pipeline error: {str(e)}"
                    await self.session.commit()
            except Exception as inner_err:
                logger.error("Failed to commit FAILED status for %s: %s", doc_uuid, inner_err)

    async def get_document_file(self, document_id: UUID, user_id: UUID) -> tuple[bytes, str, str]:
        """Retrieves raw document bytes, original filename, and content type, enforcing ownership."""
        doc = await self.doc_repo.get_by_id_and_owner(document_id, user_id)
        if not doc:
            raise AppError(
                code="DOCUMENT_NOT_FOUND",
                message="Document not found or access denied.",
                status_code=404,
            )
        file_bytes = await self.storage.load(doc.storage_key)
        return file_bytes, doc.original_filename, doc.content_type


    async def get_document(self, document_id: UUID, user_id: UUID) -> DocumentResponse:
        """Retrieves single document enforcing ownership."""
        doc = await self.doc_repo.get_by_id_and_owner(document_id, user_id)
        if not doc:
            raise AppError(
                code="DOCUMENT_NOT_FOUND",
                message="Document not found or access denied.",
                status_code=404,
            )

        chunk_count = await self.doc_repo.get_chunk_count(doc.id)
        active_ver = await self.doc_repo.get_active_version(doc.id)

        return DocumentResponse(
            id=doc.id,
            knowledge_base_id=doc.knowledge_base_id,
            owner_id=doc.owner_id,
            filename=doc.filename,
            original_filename=doc.original_filename,
            content_type=doc.content_type,
            file_size=doc.file_size,
            checksum=doc.checksum,
            storage_key=doc.storage_key,
            status=doc.status,
            ingestion_error=doc.ingestion_error,
            created_at=doc.created_at,
            updated_at=doc.updated_at,
            chunk_count=chunk_count,
            active_version=active_ver.version_number if active_ver else 1,
        )

    async def list_documents(
        self, kb_id: UUID, user_id: UUID, offset: int = 0, limit: int = 50
    ) -> tuple[list[DocumentResponse], int]:
        """Lists documents for a knowledge base enforcing ownership."""
        kb = await self.kb_repo.get_by_id_and_owner(kb_id, user_id)
        if not kb:
            raise AppError(
                code="KNOWLEDGE_BASE_NOT_FOUND",
                message="Knowledge base not found or access denied.",
                status_code=404,
            )

        docs, total = await self.doc_repo.list_by_kb(kb_id, user_id, offset=offset, limit=limit)
        response_items: list[DocumentResponse] = []

        for doc in docs:
            chunk_count = await self.doc_repo.get_chunk_count(doc.id)
            active_ver = await self.doc_repo.get_active_version(doc.id)
            response_items.append(
                DocumentResponse(
                    id=doc.id,
                    knowledge_base_id=doc.knowledge_base_id,
                    owner_id=doc.owner_id,
                    filename=doc.filename,
                    original_filename=doc.original_filename,
                    content_type=doc.content_type,
                    file_size=doc.file_size,
                    checksum=doc.checksum,
                    storage_key=doc.storage_key,
                    status=doc.status,
                    ingestion_error=doc.ingestion_error,
                    created_at=doc.created_at,
                    updated_at=doc.updated_at,
                    chunk_count=chunk_count,
                    active_version=active_ver.version_number if active_ver else 1,
                )
            )

        return response_items, total

    async def reprocess_document(self, document_id: UUID, user_id: UUID) -> DocumentResponse:
        """Cleans previous chunks and triggers re-ingestion of the stored document."""
        doc = await self.doc_repo.get_by_id_and_owner(document_id, user_id)
        if not doc:
            raise AppError(
                code="DOCUMENT_NOT_FOUND",
                message="Document not found or access denied.",
                status_code=404,
            )

        # 1. Clean previous chunks to avoid duplicate vectors
        doc.chunks.clear()
        await self.doc_repo.delete_chunks_for_document(doc.id)
        doc.status = DocumentStatus.PROCESSING
        doc.ingestion_error = None
        await self.session.flush()
        await self.session.commit()

        # 2. Execute ingestion pipeline
        await self.run_ingestion_pipeline(doc.id)
        await self.session.refresh(doc)

        chunk_count = await self.doc_repo.get_chunk_count(doc.id)
        active_ver = await self.doc_repo.get_active_version(doc.id)

        return DocumentResponse(
            id=doc.id,
            knowledge_base_id=doc.knowledge_base_id,
            owner_id=doc.owner_id,
            filename=doc.filename,
            original_filename=doc.original_filename,
            content_type=doc.content_type,
            file_size=doc.file_size,
            checksum=doc.checksum,
            storage_key=doc.storage_key,
            status=doc.status,
            ingestion_error=doc.ingestion_error,
            created_at=doc.created_at,
            updated_at=doc.updated_at,
            chunk_count=chunk_count,
            active_version=active_ver.version_number if active_ver else 1,
        )

    async def delete_document(self, document_id: UUID, user_id: UUID) -> None:
        """Deletes a document, physical file, and all associated chunks and versions."""
        doc = await self.doc_repo.get_by_id_and_owner(document_id, user_id)
        if not doc:
            raise AppError(
                code="DOCUMENT_NOT_FOUND",
                message="Document not found or access denied.",
                status_code=404,
            )

        # 1. Delete physical storage file
        if doc.storage_key:
            try:
                await self.storage.delete(doc.storage_key)
            except Exception as e:
                logger.warning("Could not delete physical storage file %s: %s", doc.storage_key, e)

        # 2. Delete database records (chunks and versions deleted via ORM cascade)
        await self.doc_repo.delete(doc)
        await self.session.flush()
        await self.session.commit()
        logger.info("Deleted document %s and cleaned up associated storage", document_id)


    async def get_document_chunks(
        self, document_id: UUID, user_id: UUID, offset: int = 0, limit: int = 50
    ) -> tuple[list[DocumentChunkResponse], int]:
        """Returns chunks for a document ensuring user ownership."""
        doc = await self.doc_repo.get_by_id_and_owner(document_id, user_id)
        if not doc:
            raise AppError(
                code="DOCUMENT_NOT_FOUND",
                message="Document not found or access denied.",
                status_code=404,
            )

        chunks, total = await self.chunk_repo.list_by_document(document_id, offset=offset, limit=limit)
        response_items = [
            DocumentChunkResponse(
                id=c.id,
                document_id=c.document_id,
                document_version_id=c.document_version_id or c.document_id,
                chunk_index=c.chunk_index,
                content=c.content,
                token_count=c.token_count,
                character_count=c.character_count,
                page_number=c.page_number,
                section_title=c.section_title,
                start_offset=c.start_offset,
                end_offset=c.end_offset,
                chunk_metadata=c.chunk_metadata or {},
                created_at=c.created_at,
            )
            for c in chunks
        ]
        return response_items, total
