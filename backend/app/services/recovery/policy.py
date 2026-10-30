"""Deterministic adaptive recovery policy for bounded self-healing orchestration."""

import time
from typing import Any

from app.core.config import settings
from app.core.logging import get_logger
from app.services.recovery.models import FailureCategory, FailureDiagnosis, RecoveryAction

logger = get_logger(__name__)


class RecoveryPolicy:
    """Enforces bounded, adaptive self-healing recovery actions with strict safety limits."""

    def __init__(
        self,
        max_attempts: int | None = None,
        timeout_seconds: float | None = None,
    ):
        self.max_attempts = max_attempts or settings.RECOVERY_MAX_ATTEMPTS
        self.timeout_seconds = timeout_seconds or settings.RECOVERY_TIMEOUT_SECONDS

    def evaluate(
        self,
        diagnosis: FailureDiagnosis,
        recovery_count: int,
        deadline: float,
        action_history: list[str] | None = None,
        query_history: list[str] | None = None,
        current_query: str = "",
    ) -> tuple[RecoveryAction, str, dict[str, Any]]:
        """Selects next allowable recovery action or enforces safe bounded termination."""
        action_history = action_history or []
        query_history = query_history or []
        now = time.time()

        # 1. Global execution deadline check
        if now >= deadline:
            return (
                RecoveryAction.TERMINATE_NON_RECOVERABLE,
                "Workflow execution timeout exceeded deadline.",
                {"timed_out": True},
            )

        # 2. Non-recoverable failure check
        if not diagnosis.is_recoverable or diagnosis.category == FailureCategory.NON_RECOVERABLE_FAILURE:
            return (
                RecoveryAction.TERMINATE_NON_RECOVERABLE,
                f"Permanent non-recoverable condition: {diagnosis.reason}",
                {"category": diagnosis.category.value},
            )

        # 3. Maximum retry budget exhaustion check
        if recovery_count >= self.max_attempts:
            if diagnosis.category in (FailureCategory.INSUFFICIENT_EVIDENCE, FailureCategory.LOW_RELEVANCE_EVIDENCE):
                return (
                    RecoveryAction.TERMINATE_INSUFFICIENT,
                    f"Recovery retry budget exhausted ({recovery_count}/{self.max_attempts}); returning honest insufficient-evidence response.",
                    {"exhausted": True},
                )
            return (
                RecoveryAction.TERMINATE_NON_RECOVERABLE,
                f"Recovery retry budget exhausted ({recovery_count}/{self.max_attempts}) on {diagnosis.category.value}.",
                {"exhausted": True},
            )

        # 4. Cycle detection & adaptive policy selection
        action = diagnosis.suggested_action

        # Cycle protection for identical actions - cascade through alternatives
        if action == RecoveryAction.REWRITE_QUERY and RecoveryAction.REWRITE_QUERY.value in action_history:
            action = RecoveryAction.EXPAND_RETRIEVAL

        if action == RecoveryAction.EXPAND_RETRIEVAL and RecoveryAction.EXPAND_RETRIEVAL.value in action_history:
            action = RecoveryAction.FALLBACK_STRATEGY

        if action == RecoveryAction.FALLBACK_STRATEGY and RecoveryAction.FALLBACK_STRATEGY.value in action_history:
            action = RecoveryAction.TERMINATE_INSUFFICIENT

        if (
            action in (RecoveryAction.RETRY_TRANSIENT, RecoveryAction.REGENERATE_WITH_FEEDBACK)
            and action.value in action_history
        ):
            action = RecoveryAction.TERMINATE_NON_RECOVERABLE

        # Specific action configurations
        params: dict[str, Any] = {}
        if action == RecoveryAction.EXPAND_RETRIEVAL:
            params["candidate_limit"] = settings.RECOVERY_EXPANSION_CANDIDATE_LIMIT
            params["top_k"] = 8
            reason = (
                f"Attempt #{recovery_count + 1}: Expanding retrieval candidate depth to {params['candidate_limit']}."
            )

        elif action == RecoveryAction.REWRITE_QUERY:
            reason = f"Attempt #{recovery_count + 1}: Reformulating query to enhance recall."

        elif action == RecoveryAction.FALLBACK_STRATEGY:
            params["mode"] = "hybrid"
            params["enable_reranking"] = True
            reason = f"Attempt #{recovery_count + 1}: Falling back to hybrid fusion strategy."

        elif action == RecoveryAction.REPAIR_CITATIONS:
            reason = f"Attempt #{recovery_count + 1}: Stripping ungrounded citations and mapping exclusively to retrieved chunks."

        elif action == RecoveryAction.REGENERATE_WITH_FEEDBACK:
            reason = f"Attempt #{recovery_count + 1}: Controlled regeneration with verification feedback."

        elif action == RecoveryAction.RETRY_TRANSIENT:
            backoff_s = settings.RECOVERY_BACKOFF_FACTOR * (2**recovery_count)
            params["backoff_seconds"] = backoff_s
            reason = f"Attempt #{recovery_count + 1}: Transient error backoff ({backoff_s:.2f}s)."

        elif action == RecoveryAction.TERMINATE_INSUFFICIENT:
            reason = "Terminating with truthful insufficient evidence response."

        else:
            reason = "Terminating recovery loop safely."

        return action, reason, params
