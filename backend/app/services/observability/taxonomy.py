"""Error classification taxonomy and diagnostic inference for Phase 10 Observability."""

from dataclasses import dataclass
from typing import Any

from app.services.observability.schemas import ErrorCategory


@dataclass
class ClassifiedError:
    """Classified diagnostic profile for an observed execution failure or anomaly."""

    category: ErrorCategory
    safe_code: str
    diagnostic_summary: str
    affected_stage: str
    retry_attempted: bool
    recovery_succeeded: bool
    suggested_action: str
    is_infrastructure_failure: bool


class ErrorClassifier:
    """Classifies errors, exceptions, and anomalies into production taxonomy categories."""

    @classmethod
    def classify(
        cls,
        error: Any,
        stage: str = "unknown",
        retry_attempted: bool = False,
        recovery_succeeded: bool = False,
        details: dict[str, Any] | None = None,
    ) -> ClassifiedError:
        """Inspects an exception, string, or code and returns a structured diagnostic classification."""
        details = details or {}
        err_str = str(error).lower() if error else ""
        code = getattr(error, "code", None) or details.get("code")

        # 1. Authentication Failure
        if (code in ("UNAUTHENTICATED", "INVALID_CREDENTIALS", "TOKEN_EXPIRED", "INVALID_TOKEN")) or (
            "token" in err_str and ("expired" in err_str or "invalid" in err_str or "missing" in err_str)
        ):
            return ClassifiedError(
                category=ErrorCategory.AUTHENTICATION_FAILURE,
                safe_code=code or "AUTH_INVALID_CREDENTIALS",
                diagnostic_summary="Authentication credentials missing, expired, or invalid.",
                affected_stage="gateway_auth",
                retry_attempted=retry_attempted,
                recovery_succeeded=recovery_succeeded,
                suggested_action="Re-authenticate with valid user credentials or refresh bearer token.",
                is_infrastructure_failure=False,
            )

        # 2. Authorization Failure
        if (code in ("PERMISSION_DENIED", "FORBIDDEN", "KNOWLEDGE_BASE_NOT_FOUND")) or (
            "access denied" in err_str or "forbidden" in err_str or "unauthorized" in err_str
        ):
            return ClassifiedError(
                category=ErrorCategory.AUTHORIZATION_FAILURE,
                safe_code=code or "AUTH_FORBIDDEN",
                diagnostic_summary="Target resource is not accessible to the requesting identity.",
                affected_stage="scope_authorization",
                retry_attempted=retry_attempted,
                recovery_succeeded=recovery_succeeded,
                suggested_action="Verify knowledge base access permissions or role configuration.",
                is_infrastructure_failure=False,
            )

        # 3. Insufficient Evidence (Critical: Not an infrastructure failure!)
        if (code in ("INSUFFICIENT_EVIDENCE", "LOW_RELEVANCE_EVIDENCE")) or (
            "insufficient" in err_str and "evidence" in err_str
        ) or (details.get("evidence_status") in ("insufficient", "low_relevance")):
            return ClassifiedError(
                category=ErrorCategory.INSUFFICIENT_EVIDENCE,
                safe_code="EVIDENCE_INSUFFICIENT",
                diagnostic_summary="Query could not be grounded because knowledge base lacks adequate relevant passages.",
                affected_stage="evidence_assessment",
                retry_attempted=retry_attempted,
                recovery_succeeded=recovery_succeeded,
                suggested_action="Upload additional relevant reference documents or broaden query terminology.",
                is_infrastructure_failure=False,
            )

        # 4. Timeout
        if (
            isinstance(error, TimeoutError)
            or "timeout" in err_str
            or code in ("TIMEOUT", "DEADLINE_EXCEEDED")
            or "timed out" in err_str
        ):
            return ClassifiedError(
                category=ErrorCategory.TIMEOUT,
                safe_code="EXECUTION_TIMEOUT",
                diagnostic_summary="Execution budget elapsed before stage completed.",
                affected_stage=stage,
                retry_attempted=retry_attempted,
                recovery_succeeded=recovery_succeeded,
                suggested_action="Check upstream provider responsiveness or increase timeout bounds.",
                is_infrastructure_failure=True,
            )

        # 5. Database Failure
        if (
            "psycopg" in err_str
            or "database" in err_str
            or "connection refused" in err_str
            or "sqlalchemy" in err_str
            or code == "DATABASE_CONNECTION_ERROR"
        ):
            return ClassifiedError(
                category=ErrorCategory.DATABASE_FAILURE,
                safe_code="DB_CONNECTIVITY_ERROR",
                diagnostic_summary="Database query or connection failure occurred.",
                affected_stage=stage,
                retry_attempted=retry_attempted,
                recovery_succeeded=recovery_succeeded,
                suggested_action="Verify PostgreSQL server status, credentials, and connection pool saturation.",
                is_infrastructure_failure=True,
            )

        # 6. Reranker Failure
        if "rerank" in err_str or code == "RERANK_FAILED" or stage == "reranking":
            return ClassifiedError(
                category=ErrorCategory.RERANKER_FAILURE,
                safe_code="RERANKER_SERVICE_ERROR",
                diagnostic_summary="Neural cross-encoder reranking service encountered an error.",
                affected_stage="reranking",
                retry_attempted=retry_attempted,
                recovery_succeeded=recovery_succeeded,
                suggested_action="Check reranker model availability or fall back to Reciprocal Rank Fusion.",
                is_infrastructure_failure=True,
            )

        # 7. Embedding Provider Failure
        if (
            ("embed" in err_str or "embedding" in err_str)
            and ("quota" in err_str or "rate" in err_str or "api" in err_str or "fail" in err_str)
        ):
            return ClassifiedError(
                category=ErrorCategory.EMBEDDING_PROVIDER_FAILURE,
                safe_code="EMBEDDING_PROVIDER_ERROR",
                diagnostic_summary="Upstream embedding service returned an error or quota exhaustion.",
                affected_stage="dense_retrieval",
                retry_attempted=retry_attempted,
                recovery_succeeded=recovery_succeeded,
                suggested_action="Verify embedding API key, quota credits, or provider rate limits.",
                is_infrastructure_failure=True,
            )

        # 8. LLM Provider Failure
        if (
            "llm" in err_str
            or "openai" in err_str
            or "gemini" in err_str
            or "anthropic" in err_str
            or "provider" in err_str
            or code == "PROVIDER_ERROR"
        ):
            return ClassifiedError(
                category=ErrorCategory.LLM_PROVIDER_FAILURE,
                safe_code="LLM_UPSTREAM_ERROR",
                diagnostic_summary="Upstream generative LLM provider failed, throttled, or timed out.",
                affected_stage=stage if stage != "unknown" else "llm_generation",
                retry_attempted=retry_attempted,
                recovery_succeeded=recovery_succeeded,
                suggested_action="Verify LLM API service health, balance, and network reachability.",
                is_infrastructure_failure=True,
            )

        # 9. Citation Validation Failure
        if code in ("CITATION_FAILURE", "UNGROUNDED_CLAIMS") or "citation" in err_str:
            return ClassifiedError(
                category=ErrorCategory.CITATION_VALIDATION_FAILURE,
                safe_code="CITATION_AUDIT_MISMATCH",
                diagnostic_summary="Generated response contained claims not strictly verifiable in retrieved sources.",
                affected_stage="citation_validation",
                retry_attempted=retry_attempted,
                recovery_succeeded=recovery_succeeded,
                suggested_action="Inspect citation audit logs or invoke the Phase 8 citation repair action.",
                is_infrastructure_failure=False,
            )

        # 10. Rate Limiting
        if "rate limit" in err_str or "429" in err_str or code == "RATE_LIMIT_EXCEEDED":
            return ClassifiedError(
                category=ErrorCategory.RATE_LIMITING,
                safe_code="RATE_LIMIT_THROTTLED",
                diagnostic_summary="Request throttled by rate limit enforcement.",
                affected_stage=stage,
                retry_attempted=retry_attempted,
                recovery_succeeded=recovery_succeeded,
                suggested_action="Apply exponential backoff or increase rate limit capacity tier.",
                is_infrastructure_failure=True,
            )

        # 11. Recovery Exhausted
        if code in ("RECOVERY_EXHAUSTED", "BUDGET_EXHAUSTED") or "recovery exhausted" in err_str:
            return ClassifiedError(
                category=ErrorCategory.RECOVERY_EXHAUSTED,
                safe_code="RECOVERY_BUDGET_EXHAUSTED",
                diagnostic_summary="Self-healing recovery engine reached maximum allowed attempt limits.",
                affected_stage="recovery_engine",
                retry_attempted=True,
                recovery_succeeded=False,
                suggested_action="Analyze intermediate failure categories in the recovery audit trail.",
                is_infrastructure_failure=False,
            )

        # 12. Retrieval Failure
        if "retrieval" in err_str or stage in ("retrieval", "dense_retrieval", "lexical_retrieval"):
            return ClassifiedError(
                category=ErrorCategory.RETRIEVAL_FAILURE,
                safe_code="RETRIEVAL_EXECUTION_ERROR",
                diagnostic_summary="Retrieval execution failed across search indices.",
                affected_stage="retrieval",
                retry_attempted=retry_attempted,
                recovery_succeeded=recovery_succeeded,
                suggested_action="Check vector index health and BM25 inverted index integrity.",
                is_infrastructure_failure=True,
            )

        # 13. Invalid Request
        if code in ("INVALID_REQUEST", "VALIDATION_ERROR") or "validation" in err_str:
            return ClassifiedError(
                category=ErrorCategory.INVALID_REQUEST,
                safe_code="REQUEST_SCHEMA_INVALID",
                diagnostic_summary="Request payload contains invalid fields or parameters.",
                affected_stage="request_validation",
                retry_attempted=False,
                recovery_succeeded=False,
                suggested_action="Correct client request format according to API schema specifications.",
                is_infrastructure_failure=False,
            )

        # Default fallback: Unexpected Internal Error
        return ClassifiedError(
            category=ErrorCategory.UNEXPECTED_INTERNAL_ERROR,
            safe_code="INTERNAL_SERVER_ERROR",
            diagnostic_summary=f"An unhandled execution anomaly occurred: {err_str[:120]}",
            affected_stage=stage,
            retry_attempted=retry_attempted,
            recovery_succeeded=recovery_succeeded,
            suggested_action="Review server application logs with the correlated Trace ID.",
            is_infrastructure_failure=True,
        )
