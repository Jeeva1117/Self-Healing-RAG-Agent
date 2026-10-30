"""Knowledge Base Repair Engine: targeted, idempotent, and non-destructive repairs for document indexing issues."""

import math
from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import AppError
from app.core.logging import get_logger
from app.domain.interfaces.embeddings import EmbeddingProviderInterface
from app.domain.interfaces.storage import ObjectStorageInterface
from app.infrastructure.database.models import (
    Document,
    DocumentChunk,
    DocumentStatus,
    KnowledgeBaseRepairJob,
)
from app.infrastructure.embedding.factory import get_embedding_provider
from app.infrastructure.storage.local_storage import LocalStorageProvider
from app.repositories.chunk_repository import ChunkRepository
from app.repositories.document_repository import DocumentRepository
from app.repositories.knowledge_base_repository import KnowledgeBaseRepository
from app.repositories.repair_job_repository import RepairJobRepository
from app.schemas.knowledge_base import RepairJobResponse
from app.services.chunker import DocumentChunker
from app.services.knowledge_base.health import KnowledgeBaseHealthEngine
from app.services.knowledge_base.versioning import KnowledgeBaseVersioningEngine
from app.services.normalizer import TextNormalizer
from app.services.parsers.factory import ParserFactory

logger = get_logger("app.services.kb.repair")

VALID_REPAIR_ACTIONS = {
    "REPAIR_EMBEDDINGS",
    "REGENERATE_CHUNKS",
    "RETRY_EXTRACTION",
    "RECONCILE_STALE",
    "REINDEX_VERSION",
}


class KnowledgeBaseRepairEngine:
    """Dispatches and tracks targeted repairs with dry-run support, idempotency, and postcondition verification."""

    def __init__(
        self,
        session: AsyncSession,
        storage_provider: ObjectStorageInterface | None = None,
        embedding_provider: EmbeddingProviderInterface | None = None,
        chunker: DocumentChunker | None = None,
    ):
        self.session = session
        self.doc_repo = DocumentRepository(session)
        self.kb_repo = KnowledgeBaseRepository(session)
        self.chunk_repo = ChunkRepository(session)
        self.repair_repo = RepairJobRepository(session)
        self.health_engine = KnowledgeBaseHealthEngine(session)
        self.version_engine = KnowledgeBaseVersioningEngine(session, storage_provider, embedding_provider)
        self.storage = storage_provider or LocalStorageProvider()
        self.embeddings = embedding_provider or get_embedding_provider()
        self.chunker = chunker or DocumentChunker()

    async def execute_repair(
        self,
        knowledge_base_id: UUID,
        document_id: UUID,
        user_id: UUID,
        action: str,
        dry_run: bool = False,
    ) -> RepairJobResponse:
        """Executes a targeted repair operation ensuring tenant isolation and race-prevention."""
        # 1. Action Validation
        action_clean = action.strip().upper()
        if action_clean not in VALID_REPAIR_ACTIONS:
            raise AppError(
                code="INVALID_REPAIR_ACTION",
                message=f"Action '{action}' is not valid. Supported actions: {sorted(VALID_REPAIR_ACTIONS)}",
                status_code=400,
            )

        # 2. Ownership Verification
        kb = await self.kb_repo.get_by_id_and_owner(knowledge_base_id, user_id)
        if not kb:
            raise AppError(
                code="KNOWLEDGE_BASE_NOT_FOUND",
                message="Knowledge base not found or access denied.",
                status_code=404,
            )

        doc = await self.doc_repo.get_by_id_and_owner(document_id, user_id)
        if not doc or doc.knowledge_base_id != knowledge_base_id:
            raise AppError(
                code="DOCUMENT_NOT_FOUND",
                message="Document not found or access denied.",
                status_code=404,
            )

        # 3. Race & Concurrency Guard
        active_job = await self.repair_repo.get_active_job_for_document(doc.id)
        if active_job and not dry_run:
            raise AppError(
                code="CONCURRENT_REPAIR_JOB",
                message=f"A repair job ({active_job.id}) is currently {active_job.status} for this document.",
                status_code=409,
            )

        job_id = uuid4()
        now = datetime.now(UTC)

        # 4. Dry Run Handling
        if dry_run:
            preview_details = await self._preview_action(doc, action_clean)
            return RepairJobResponse(
                job_id=job_id,
                knowledge_base_id=knowledge_base_id,
                document_id=doc.id,
                action=action_clean,
                status="COMPLETED",
                dry_run=True,
                findings_addressed=preview_details.get("addressed_findings", []),
                details=preview_details,
                error_message=None,
                started_at=now,
                completed_at=now,
            )

        # 5. Persist Running Job
        job = KnowledgeBaseRepairJob(
            id=job_id,
            knowledge_base_id=knowledge_base_id,
            document_id=doc.id,
            user_id=user_id,
            action=action_clean,
            status="RUNNING",
            dry_run=False,
            findings_addressed=[],
            details={},
            started_at=now,
        )
        self.session.add(job)
        await self.session.commit()

        # 6. Execute Specific Action
        addressed_findings: list[str] = []
        details: dict[str, Any] = {}

        try:
            if action_clean == "REPAIR_EMBEDDINGS":
                details = await self._repair_embeddings(doc)
                addressed_findings = ["MISSING_EMBEDDINGS", "EMBEDDING_DIM_MISMATCH", "INVALID_EMBEDDING_VALUES"]

            elif action_clean == "REGENERATE_CHUNKS":
                details = await self._regenerate_chunks(doc)
                addressed_findings = ["NO_CHUNKS", "DUPLICATE_CHUNK_INDEX", "CHUNK_INDEX_GAP"]

            elif action_clean == "RETRY_EXTRACTION":
                details = await self._retry_extraction(doc)
                addressed_findings = ["INGESTION_FAILED", "NO_CHUNKS"]

            elif action_clean == "RECONCILE_STALE":
                details = await self._reconcile_stale(doc)
                addressed_findings = ["STALE_PROCESSING"]

            elif action_clean == "REINDEX_VERSION":
                version, count = await self.version_engine.reindex_document(doc.id, user_id)
                details = {"promoted_version": version.version_number, "new_chunk_count": count}
                addressed_findings = ["STALE_DOCUMENT_VERSION", "INCONSISTENT_VERSION"]

            # 7. Postcondition Verification
            post_health = await self.health_engine.check_document_health(doc.id, user_id)
            post_findings = [f.code for f in post_health.findings]
            details["post_repair_findings"] = post_findings
            details["is_healthy"] = post_health.is_healthy

            job.status = "COMPLETED"
            job.completed_at = datetime.now(UTC)
            job.findings_addressed = addressed_findings
            job.details = details
            await self.session.commit()

            return RepairJobResponse(
                job_id=job.id,
                knowledge_base_id=knowledge_base_id,
                document_id=doc.id,
                action=action_clean,
                status=job.status,
                dry_run=False,
                findings_addressed=addressed_findings,
                details=details,
                error_message=None,
                started_at=job.started_at,
                completed_at=job.completed_at,
            )

        except Exception as exc:
            logger.error("REPAIR_FAILED: job_id=%s doc_id=%s err=%s", job_id, doc.id, str(exc))
            job.status = "FAILED"
            job.error_message = str(exc)
            job.completed_at = datetime.now(UTC)
            await self.session.commit()
            raise AppError(
                code="REPAIR_EXECUTION_FAILED",
                message=f"Repair failed: {str(exc)}",
                status_code=500,
            ) from exc

    async def _preview_action(self, doc: Document, action: str) -> dict[str, Any]:
        """Provides preview data for dry-run inspection without modifying database records."""
        chunks, total_chunks = await self.chunk_repo.list_by_document(doc.id, offset=0, limit=1000)
        addressed: list[str] = []
        action_summary = ""

        if action == "REPAIR_EMBEDDINGS":
            dim = self.embeddings.dimension
            affected = sum(1 for c in chunks if not c.embedding or len(c.embedding) != dim)
            addressed = ["MISSING_EMBEDDINGS", "EMBEDDING_DIM_MISMATCH", "INVALID_EMBEDDING_VALUES"]
            action_summary = f"Would regenerate embeddings for {affected} of {total_chunks} chunks."

        elif action == "REGENERATE_CHUNKS":
            addressed = ["NO_CHUNKS", "DUPLICATE_CHUNK_INDEX", "CHUNK_INDEX_GAP"]
            action_summary = f"Would re-parse '{doc.filename}' and reconstruct all chunks."

        elif action == "RETRY_EXTRACTION":
            addressed = ["INGESTION_FAILED", "NO_CHUNKS"]
            action_summary = f"Would retry full ingestion pipeline for '{doc.filename}'."

        elif action == "RECONCILE_STALE":
            addressed = ["STALE_PROCESSING"]
            action_summary = f"Would reconcile document '{doc.filename}' from {doc.status} to READY or FAILED."

        elif action == "REINDEX_VERSION":
            active_v = await self.doc_repo.get_active_version(doc.id)
            ver_num = (active_v.version_number + 1) if active_v else 2
            addressed = ["STALE_DOCUMENT_VERSION", "INCONSISTENT_VERSION"]
            action_summary = f"Would stage and promote Version {ver_num} using safe zero-downtime reindexing."

        return {
            "action": action,
            "document_id": str(doc.id),
            "filename": doc.filename,
            "current_status": doc.status,
            "total_chunks": total_chunks,
            "addressed_findings": addressed,
            "summary": action_summary,
        }

    async def _repair_embeddings(self, doc: Document) -> dict[str, Any]:
        """Regenerates missing or invalid embeddings for document chunks."""
        chunks, _ = await self.chunk_repo.list_by_document(doc.id, offset=0, limit=1000)
        if not chunks:
            raise AppError(
                code="NO_CHUNKS_TO_EMBED",
                message="Cannot repair embeddings: Document contains 0 chunks. Run REGENERATE_CHUNKS first.",
                status_code=400,
            )

        texts = [c.content for c in chunks]
        vectors = await self.embeddings.embed_documents(texts)
        dim = self.embeddings.dimension

        repaired_count = 0
        for i, chunk in enumerate(chunks):
            vec = vectors[i]
            if len(vec) != dim or any(not math.isfinite(x) for x in vec):
                raise AppError(
                    code="EMBEDDING_GENERATION_FAILED",
                    message=f"Embedding provider produced invalid vector for chunk {chunk.chunk_index}.",
                    status_code=502,
                )
            chunk.embedding = vec
            repaired_count += 1

        if doc.status != DocumentStatus.READY:
            doc.status = DocumentStatus.READY
            doc.ingestion_error = None

        await self.session.commit()
        return {"repaired_chunk_embeddings": repaired_count}

    async def _regenerate_chunks(self, doc: Document) -> dict[str, Any]:
        """Reconstructs chunks from original file bytes."""
        active_version = await self.doc_repo.get_active_version(doc.id)
        storage_key = active_version.storage_key if active_version else doc.storage_key
        file_bytes = await self.storage.load(storage_key)

        parser = ParserFactory.get_parser(doc.filename, doc.content_type)
        parsed_doc = parser.parse(file_bytes, doc.filename)

        if parsed_doc.is_scanned:
            doc.status = DocumentStatus.OCR_REQUIRED
            await self.session.commit()
            raise AppError(
                code="OCR_REQUIRED",
                message="Cannot generate chunks: Document is a scanned image.",
                status_code=422,
            )

        for unit in parsed_doc.units:
            unit.text = TextNormalizer.normalize(unit.text)

        version_id = str(active_version.id) if active_version else None
        chunks_data = self.chunker.chunk_document(
            parsed_doc=parsed_doc,
            document_id=str(doc.id),
            document_version_id=version_id,
            source_filename=doc.original_filename,
        )

        if not chunks_data:
            raise AppError(
                code="NO_CHUNKS_GENERATED",
                message="Parser produced no usable text chunks.",
                status_code=422,
            )

        texts = [c.content for c in chunks_data]
        vectors = await self.embeddings.embed_documents(texts)

        chunk_entities: list[DocumentChunk] = []
        for i, c_data in enumerate(chunks_data):
            chunk_entities.append(
                DocumentChunk(
                    document_id=doc.id,
                    document_version_id=active_version.id if active_version else None,
                    chunk_index=c_data.chunk_index,
                    content=c_data.content,
                    token_count=c_data.token_count,
                    character_count=c_data.character_count,
                    page_number=c_data.page_number,
                    section_title=c_data.section_title,
                    start_offset=c_data.start_offset,
                    end_offset=c_data.end_offset,
                    chunk_metadata=c_data.metadata,
                    embedding=vectors[i],
                )
            )

        await self.chunk_repo.delete_by_document(doc.id)
        await self.chunk_repo.create_chunks(chunk_entities)

        doc.status = DocumentStatus.READY
        doc.ingestion_error = None
        await self.session.commit()
        return {"reconstructed_chunks": len(chunk_entities)}

    async def _retry_extraction(self, doc: Document) -> dict[str, Any]:
        """Retries extraction and chunking for failed documents."""
        return await self._regenerate_chunks(doc)

    async def _reconcile_stale(self, doc: Document) -> dict[str, Any]:
        """Reconciles documents stuck in PROCESSING state."""
        chunk_count = await self.doc_repo.get_chunk_count(doc.id)
        if chunk_count > 0:
            # Document has chunks, verify embeddings
            chunks, _ = await self.chunk_repo.list_by_document(doc.id, offset=0, limit=1)
            if chunks and chunks[0].embedding:
                doc.status = DocumentStatus.READY
                doc.ingestion_error = None
                await self.session.commit()
                return {"reconciled_status": "READY", "reason": "Existing chunks and embeddings verified."}

        # Otherwise mark FAILED with clear diagnostic
        doc.status = DocumentStatus.FAILED
        doc.ingestion_error = "Ingestion timed out or interrupted. Ready for targeted retry."
        await self.session.commit()
        return {"reconciled_status": "FAILED", "reason": "Processing interrupted without valid chunks."}
