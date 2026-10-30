"""Failure classification engine for diagnosing RAG pipeline execution errors."""

from typing import Any

from app.core.logging import get_logger
from app.services.recovery.models import FailureCategory, FailureDiagnosis, RecoveryAction

logger = get_logger(__name__)

TRANSIENT_ERROR_KEYWORDS = (
    "timeout",
    "timed out",
    "connection refused",
    "connection error",
    "network",
    "deadlock",
    "lock wait",
    "temporary",
    "retry",
    "503",
    "502",
    "504",
    "429",
    "rate limit",
    "too many requests",
    "overloaded",
    "transient",
)

PERMANENT_ERROR_KEYWORDS = (
    "access denied",
    "not found",
    "unauthorized",
    "permission",
    "401",
    "403",
    "404",
    "invalid token",
    "forbidden",
    "not authenticated",
)


class FailureClassifier:
    """Classifies runtime pipeline anomalies into typed failure categories."""

    @staticmethod
    def classify_retrieval(
        error: Exception | str | None = None,
        results: list[Any] | None = None,
        query: str = "",
        terms: list[str] | None = None,
    ) -> FailureDiagnosis:
        """Diagnoses retrieval outcomes based on exceptions, candidate counts, and relevance signals."""
        results = results or []
        terms = terms or []

        # 1. Exception-based diagnosis
        if error is not None:
            err_str = str(error).lower()

            if any(p in err_str for p in PERMANENT_ERROR_KEYWORDS):
                return FailureDiagnosis(
                    category=FailureCategory.NON_RECOVERABLE_FAILURE,
                    reason=f"Permanent authorization or scope failure: {error}",
                    is_recoverable=False,
                    suggested_action=RecoveryAction.TERMINATE_NON_RECOVERABLE,
                    details={"error": str(error)},
                )

            if any(t in err_str for t in TRANSIENT_ERROR_KEYWORDS):
                return FailureDiagnosis(
                    category=FailureCategory.RETRIEVAL_FAILURE,
                    reason=f"Transient retrieval error encountered: {error}",
                    is_recoverable=True,
                    suggested_action=RecoveryAction.RETRY_TRANSIENT,
                    details={"error": str(error), "is_transient": True},
                )

            return FailureDiagnosis(
                category=FailureCategory.RETRIEVAL_FAILURE,
                reason=f"Retrieval execution failure: {error}",
                is_recoverable=True,
                suggested_action=RecoveryAction.FALLBACK_STRATEGY,
                details={"error": str(error)},
            )

        # 2. Empty results diagnosis
        if not results:
            if terms:
                return FailureDiagnosis(
                    category=FailureCategory.LOW_RELEVANCE_EVIDENCE,
                    reason="No candidate chunks retrieved matching query search terms; query rewrite recommended.",
                    is_recoverable=True,
                    suggested_action=RecoveryAction.REWRITE_QUERY,
                    details={"extracted_terms": terms},
                )
            return FailureDiagnosis(
                category=FailureCategory.INSUFFICIENT_EVIDENCE,
                reason="Knowledge base contains no matching documents for question.",
                is_recoverable=False,
                suggested_action=RecoveryAction.TERMINATE_INSUFFICIENT,
            )

        # 3. Low relevance evidence check
        # Check if any chunk matches query terms or has acceptable neural reranker score
        matched_any_term = False
        max_rerank_score = 0.0

        for item in results:
            content = getattr(item, "content", "").lower()
            section = getattr(item, "section_title", "") or ""
            c_text = content + " " + section.lower()

            if any(t.lower() in c_text for t in terms):
                matched_any_term = True

            score = getattr(item, "reranker_score", None) or getattr(item, "score", None) or 0.0
            if score > max_rerank_score:
                max_rerank_score = score

        if not matched_any_term and max_rerank_score < 0.05:
            return FailureDiagnosis(
                category=FailureCategory.LOW_RELEVANCE_EVIDENCE,
                reason=f"Retrieved {len(results)} chunks lack topical overlap with question keywords (max score: {max_rerank_score:.3f}).",
                is_recoverable=True,
                suggested_action=RecoveryAction.REWRITE_QUERY,
                details={"max_rerank_score": max_rerank_score, "chunk_count": len(results)},
            )

        return FailureDiagnosis(
            category=FailureCategory.INSUFFICIENT_EVIDENCE,
            reason="Retrieved evidence is partially relevant but may be insufficient.",
            is_recoverable=True,
            suggested_action=RecoveryAction.EXPAND_RETRIEVAL,
            details={"chunk_count": len(results), "max_rerank_score": max_rerank_score},
        )

    @staticmethod
    def classify_generation(
        error: Exception | str | None = None,
        raw_answer: str = "",
        is_insufficient: bool = False,
    ) -> FailureDiagnosis:
        """Diagnoses answer generation outcomes and provider errors."""
        if error is not None:
            err_str = str(error).lower()

            if any(p in err_str for p in PERMANENT_ERROR_KEYWORDS):
                return FailureDiagnosis(
                    category=FailureCategory.NON_RECOVERABLE_FAILURE,
                    reason=f"Generation rejected due to invalid credentials or permissions: {error}",
                    is_recoverable=False,
                    suggested_action=RecoveryAction.TERMINATE_NON_RECOVERABLE,
                    details={"error": str(error)},
                )

            is_transient = any(t in err_str for t in TRANSIENT_ERROR_KEYWORDS)
            return FailureDiagnosis(
                category=FailureCategory.GENERATION_FAILURE,
                reason=f"LLM provider error: {error}",
                is_recoverable=is_transient,
                suggested_action=RecoveryAction.RETRY_TRANSIENT
                if is_transient
                else RecoveryAction.TERMINATE_NON_RECOVERABLE,
                details={"error": str(error), "is_transient": is_transient},
            )

        if is_insufficient or "not find sufficient matching information" in raw_answer.lower():
            return FailureDiagnosis(
                category=FailureCategory.INSUFFICIENT_EVIDENCE,
                reason="Grounded generation reported insufficient reference material.",
                is_recoverable=True,
                suggested_action=RecoveryAction.EXPAND_RETRIEVAL,
            )

        return FailureDiagnosis(
            category=FailureCategory.GENERATION_FAILURE,
            reason="Grounded answer generation produced unverified or empty output.",
            is_recoverable=True,
            suggested_action=RecoveryAction.REGENERATE_WITH_FEEDBACK,
        )

    @staticmethod
    def classify_citations(
        validation_passed: bool,
        used_source_count: int = 0,
        unmapped_indices: list[int] | None = None,
    ) -> FailureDiagnosis:
        """Diagnoses citation validation and provenance auditing outcomes."""
        unmapped = unmapped_indices or []
        if not validation_passed or unmapped:
            return FailureDiagnosis(
                category=FailureCategory.CITATION_FAILURE,
                reason=f"Answer referenced ungrounded citation indexes: {unmapped}",
                is_recoverable=True,
                suggested_action=RecoveryAction.REPAIR_CITATIONS,
                details={"unmapped_indices": unmapped, "used_source_count": used_source_count},
            )

        return FailureDiagnosis(
            category=FailureCategory.CITATION_FAILURE,
            reason="Citation validation failed.",
            is_recoverable=True,
            suggested_action=RecoveryAction.REPAIR_CITATIONS,
        )

    @staticmethod
    def classify_verification(
        verification_passed: bool,
        feedback: str | None = None,
    ) -> FailureDiagnosis:
        """Diagnoses answer verification and factuality audit results."""
        if not verification_passed:
            return FailureDiagnosis(
                category=FailureCategory.VERIFICATION_FAILURE,
                reason=feedback or "Answer verification failed due to ungrounded or off-topic claims.",
                is_recoverable=True,
                suggested_action=RecoveryAction.REGENERATE_WITH_FEEDBACK,
                details={"feedback": feedback},
            )

        return FailureDiagnosis(
            category=FailureCategory.VERIFICATION_FAILURE,
            reason="Verification anomaly.",
            is_recoverable=False,
            suggested_action=RecoveryAction.TERMINATE_NON_RECOVERABLE,
        )
