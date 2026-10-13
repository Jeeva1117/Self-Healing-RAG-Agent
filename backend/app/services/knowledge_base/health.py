"""Knowledge Base Health Engine: validates document and chunk integrity, embedding validity, and versioning consistency."""

import math
from datetime import UTC, datetime, timedelta
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.exceptions import AppError
from app.core.logging import get_logger
from app.infrastructure.database.models import (
    DocumentChunk,
    DocumentStatus,
)
from app.repositories.chunk_repository import ChunkRepository
from app.repositories.document_repository import DocumentRepository
from app.repositories.knowledge_base_repository import KnowledgeBaseRepository
from app.schemas.knowledge_base import (
    DocumentHealthReport,
    HealthFinding,
    KnowledgeBaseHealthReport,
)

logger = get_logger("app.services.kb.health")


class KnowledgeBaseHealthEngine:
    """Evaluates granular, explainable, and testable health conditions across documents and chunks."""

    def __init__(self, session: AsyncSession):
        self.session = session
        self.doc_repo = DocumentRepository(session)
        self.kb_repo = KnowledgeBaseRepository(session)
        self.chunk_repo = ChunkRepository(session)

    async def check_document_health(self, document_id: UUID, user_id: UUID) -> DocumentHealthReport:
        """Evaluates health invariants for a single document, enforcing user ownership."""
        doc = await self.doc_repo.get_by_id_and_owner(document_id, user_id)
        if not doc:
            raise AppError(
                code="DOCUMENT_NOT_FOUND",
                message="Document not found or access denied.",
                status_code=404,
            )

        findings: list[HealthFinding] = []

        # 1. Lifecycle Status Checks
        if doc.status == DocumentStatus.FAILED.value or doc.status == DocumentStatus.FAILED:
            findings.append(
                HealthFinding(
                    code="INGESTION_FAILED",
                    severity="error",
                    title="Ingestion Pipeline Failed",
                    message=doc.ingestion_error or "Document failed during extraction, parsing, or chunking.",
                    remediation="Retry document ingestion or inspect the source file format.",
                    is_repairable=True,
                    affected_entity="document",
                )
            )
        elif doc.status == DocumentStatus.OCR_REQUIRED.value or doc.status == DocumentStatus.OCR_REQUIRED:
            findings.append(
                HealthFinding(
                    code="OCR_REQUIRED",
                    severity="warning",
                    title="Scanned Document / OCR Required",
                    message=doc.ingestion_error or "Document contains scanned raster images without digital text.",
                    remediation="Convert document to text-extractable format or process via OCR before ingestion.",
                    is_repairable=False,
                    affected_entity="document",
                )
            )
        elif doc.status == DocumentStatus.PROCESSING.value or doc.status == DocumentStatus.PROCESSING:
            # Check if stuck in processing (> 15 minutes)
            now = datetime.now(UTC)
            updated_at = doc.updated_at if doc.updated_at.tzinfo else doc.updated_at.replace(tzinfo=UTC)
            if now - updated_at > timedelta(minutes=15):
                findings.append(
                    HealthFinding(
                        code="STALE_PROCESSING",
                        severity="error",
                        title="Document Stuck in Processing",
                        message=f"Document has been in PROCESSING status for over 15 minutes (since {updated_at.isoformat()}).",
                        remediation="Reconcile stale processing state and retry ingestion.",
                        is_repairable=True,
                        affected_entity="document",
                    )
                )

        # 2. File and Extracted Size Constraints
        if doc.file_size == 0:
            findings.append(
                HealthFinding(
                    code="EMPTY_FILE",
                    severity="error",
                    title="Empty File Size",
                    message="Document file size is recorded as 0 bytes.",
                    remediation="Re-upload the document with valid non-empty content.",
                    is_repairable=False,
                    affected_entity="document",
                )
            )
        elif doc.file_size < 100:
            findings.append(
                HealthFinding(
                    code="DOCUMENT_TOO_SHORT",
                    severity="warning",
                    title="Extremely Short Document",
                    message=f"Document size ({doc.file_size} bytes) is unusually small and may contain insufficient context.",
                    remediation="Verify that the document contains complete operational context.",
                    is_repairable=False,
                    affected_entity="document",
                )
            )

        # 3. Chunk and Embedding Invariants
        chunks_stmt = (
            select(DocumentChunk)
            .where(DocumentChunk.document_id == doc.id)
            .order_by(DocumentChunk.chunk_index.asc())
        )
        chunks_res = await self.session.execute(chunks_stmt)
        chunks = list(chunks_res.scalars().all())

        if doc.status in (DocumentStatus.READY.value, DocumentStatus.READY) and len(chunks) == 0:
            findings.append(
                HealthFinding(
                    code="NO_CHUNKS",
                    severity="error",
                    title="Missing Indexed Chunks",
                    message="Document is marked as READY but contains zero indexed chunks in the database.",
                    remediation="Trigger document chunk regeneration and embedding generation.",
                    is_repairable=True,
                    affected_entity="chunk",
                )
            )

        # Evaluate chunk sequence and embeddings
        missing_embeddings = 0
        dim_mismatches = 0
        invalid_values = 0
        seen_indices = set()
        has_index_gaps = False

        expected_dim = getattr(settings, "EMBEDDING_DIMENSION", 384)

        for i, chk in enumerate(chunks):
            # Check index uniqueness and continuity
            if chk.chunk_index in seen_indices:
                findings.append(
                    HealthFinding(
                        code="DUPLICATE_CHUNK_INDEX",
                        severity="warning",
                        title=f"Duplicate Chunk Index ({chk.chunk_index})",
                        message=f"Multiple chunks share index {chk.chunk_index} for document {doc.filename}.",
                        remediation="Regenerate chunks to establish strict sequential indices.",
                        is_repairable=True,
                        affected_entity="chunk",
                    )
                )
            seen_indices.add(chk.chunk_index)

            if chk.chunk_index != i:
                has_index_gaps = True

            # Embedding check
            vec = chk.embedding
            if vec is None:
                missing_embeddings += 1
            else:
                if len(vec) != expected_dim:
                    dim_mismatches += 1
                for val in vec:
                    if math.isnan(val) or math.isinf(val):
                        invalid_values += 1
                        break

        if has_index_gaps and len(chunks) > 0:
            findings.append(
                HealthFinding(
                    code="CHUNK_INDEX_GAP",
                    severity="warning",
                    title="Non-Contiguous Chunk Indices",
                    message="Chunk indices contain gaps or out-of-order sequences.",
                    remediation="Re-index document to re-sequence chunks sequentially.",
                    is_repairable=True,
                    affected_entity="chunk",
                )
            )

        if missing_embeddings > 0:
            findings.append(
                HealthFinding(
                    code="MISSING_EMBEDDINGS",
                    severity="error",
                    title=f"Missing Embeddings ({missing_embeddings} Chunks)",
                    message=f"{missing_embeddings} of {len(chunks)} chunks have null vector embeddings and cannot be searched.",
                    remediation="Generate missing vector embeddings for un-embedded chunks.",
                    is_repairable=True,
                    affected_entity="chunk",
                )
            )

        if dim_mismatches > 0:
            findings.append(
                HealthFinding(
                    code="EMBEDDING_DIM_MISMATCH",
                    severity="error",
                    title="Embedding Dimension Mismatch",
                    message=f"{dim_mismatches} chunks have vector lengths inconsistent with configured model dimension ({expected_dim}).",
                    remediation="Regenerate embeddings with the active embedding model.",
                    is_repairable=True,
                    affected_entity="chunk",
                )
            )

        if invalid_values > 0:
            findings.append(
                HealthFinding(
                    code="INVALID_EMBEDDING_VALUES",
                    severity="error",
                    title="Non-Finite Embedding Numbers Detected",
                    message=f"{invalid_values} chunks contain NaN or Infinity vector components, corrupting cosine distance calculations.",
                    remediation="Recompute clean vector embeddings.",
                    is_repairable=True,
                    affected_entity="chunk",
                )
            )

        # 4. Versioning Invariants
        active_version = await self.doc_repo.get_active_version(doc.id)
        if not active_version and doc.status in (DocumentStatus.READY.value, DocumentStatus.READY):
            findings.append(
                HealthFinding(
                    code="INCONSISTENT_VERSION",
                    severity="error",
                    title="No Active Document Version",
                    message="Document has no active DocumentVersion snapshot marked is_active=True.",
                    remediation="Re-index document to establish an active version lineage.",
                    is_repairable=True,
                    affected_entity="version",
                )
            )

        # Determine overall embedding status
        if missing_embeddings == 0 and len(chunks) > 0 and dim_mismatches == 0 and invalid_values == 0:
            emb_status = "valid"
        elif missing_embeddings > 0:
            emb_status = "missing"
        elif dim_mismatches > 0 or invalid_values > 0:
            emb_status = "inconsistent"
        else:
            emb_status = "none"

        has_error = any(f.severity == "error" for f in findings)
        is_healthy = not has_error and doc.status in (DocumentStatus.READY.value, DocumentStatus.READY)

        return DocumentHealthReport(
            document_id=doc.id,
            filename=doc.original_filename,
            status=doc.status,
            is_healthy=is_healthy,
            findings=findings,
            chunk_count=len(chunks),
            active_version=active_version.version_number if active_version else 1,
            embedding_status=emb_status,
            last_indexed_at=doc.updated_at if doc.status in (DocumentStatus.READY.value, DocumentStatus.READY) else None,
        )

    async def check_kb_health(self, kb_id: UUID, user_id: UUID) -> KnowledgeBaseHealthReport:
        """Evaluates collection-wide health across all documents in a knowledge base."""
        kb = await self.kb_repo.get_by_id_and_owner(kb_id, user_id)
        if not kb:
            raise AppError(
                code="KNOWLEDGE_BASE_NOT_FOUND",
                message="Knowledge base not found or access denied.",
                status_code=404,
            )

        # List all documents in KB
        docs, total_docs = await self.doc_repo.list_by_kb(kb.id, user_id, offset=0, limit=1000)

        doc_reports: list[DocumentHealthReport] = []
        healthy_count = 0
        unhealthy_count = 0
        stuck_count = 0
        missing_emb_total = 0
        findings_summary: dict[str, int] = {}
        all_findings: list[HealthFinding] = []

        total_chunks = 0
        for doc in docs:
            report = await self.check_document_health(doc.id, user_id)
            doc_reports.append(report)
            total_chunks += report.chunk_count

            if report.is_healthy:
                healthy_count += 1
            else:
                unhealthy_count += 1

            if any(f.code == "STALE_PROCESSING" for f in report.findings):
                stuck_count += 1

            if report.embedding_status in ("missing", "inconsistent"):
                missing_emb_total += 1

            for f in report.findings:
                findings_summary[f.code] = findings_summary.get(f.code, 0) + 1
                all_findings.append(f)

        # Check for Orphaned Chunks in Knowledge Base
        # Any chunk where document_id is not in docs
        doc_ids = [d.id for d in docs]
        if doc_ids:
            orphans_stmt = (
                select(func.count(DocumentChunk.id))
                .where(
                    DocumentChunk.document_id.not_in(doc_ids),
                    DocumentChunk.document_version_id.is_(None),
                )
            )
            # Safe boundary check
            try:
                orphan_count = (await self.session.execute(orphans_stmt)).scalar_one()
                if orphan_count > 0:
                    orph_finding = HealthFinding(
                        code="ORPHANED_CHUNKS",
                        severity="warning",
                        title=f"Orphaned Chunks Detected ({orphan_count})",
                        message=f"{orphan_count} chunk records exist without a valid parent document association.",
                        remediation="Run knowledge base chunk reconciliation.",
                        is_repairable=True,
                        affected_entity="chunk",
                    )
                    all_findings.append(orph_finding)
                    findings_summary["ORPHANED_CHUNKS"] = orphan_count
            except Exception as e:
                logger.warning("Could not check orphaned chunks: %s", e)

        return KnowledgeBaseHealthReport(
            knowledge_base_id=kb.id,
            total_documents=total_docs,
            healthy_documents=healthy_count,
            unhealthy_documents=unhealthy_count,
            stuck_documents=stuck_count,
            total_chunks=total_chunks,
            missing_embeddings_count=missing_emb_total,
            findings_summary=findings_summary,
            findings=all_findings[:50],  # Bounded top findings
            documents=doc_reports,
        )

    check_knowledge_base_health = check_kb_health

