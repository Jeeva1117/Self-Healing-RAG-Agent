"""Reliability metric calculation and percentile aggregation engine for Phase 10."""

import math
from collections.abc import Sequence

from app.services.observability.schemas import ReliabilityMetrics, TraceRecord


def compute_percentile(sorted_values: Sequence[float], percentile: float) -> float:
    """Computes accurate percentile using standard nearest-rank / linear interpolation."""
    if not sorted_values:
        return 0.0
    if len(sorted_values) == 1:
        return sorted_values[0]

    k = (len(sorted_values) - 1) * (percentile / 100.0)
    f = math.floor(k)
    c = math.ceil(k)
    if f == c:
        return sorted_values[int(k)]
    d0 = sorted_values[int(f)] * (c - k)
    d1 = sorted_values[int(c)] * (k - f)
    return round(d0 + d1, 2)


class MetricsCalculator:
    """Computes real runtime reliability metrics with safeguards against low-sample bias."""

    MIN_PERCENTILE_SAMPLE_SIZE = 3

    @classmethod
    def calculate(cls, traces: Sequence[TraceRecord]) -> ReliabilityMetrics:
        """Aggregates a sequence of execution traces into a ReliabilityMetrics snapshot."""
        total = len(traces)
        if total == 0:
            return ReliabilityMetrics(
                total_requests=0,
                successful_requests=0,
                failed_requests=0,
                recovered_requests=0,
                error_rate=0.0,
                workflow_completion_rate=0.0,
                workflow_failure_rate=0.0,
            )

        successful = 0
        failed = 0
        recovered = 0
        timeout_count = 0
        insufficient_evidence_count = 0
        empty_retrieval_count = 0
        citation_validation_failure_count = 0
        llm_provider_errors = 0
        embedding_provider_errors = 0
        db_errors = 0
        total_retries = 0

        durations: list[float] = []
        retrieval_durations: list[float] = []
        rerank_durations: list[float] = []
        generation_durations: list[float] = []
        citation_durations: list[float] = []
        recovery_durations: list[float] = []

        stage_totals: dict[str, float] = {}
        stage_counts: dict[str, int] = {}

        for tr in traces:
            status = tr.status.lower()
            if status in ("completed", "success"):
                successful += 1
            elif status == "recovered":
                recovered += 1
                successful += 1
            else:
                failed += 1

            durations.append(tr.duration_ms)
            total_retries += tr.recovery_count

            if tr.error_category:
                cat = tr.error_category.lower()
                if "timeout" in cat:
                    timeout_count += 1
                elif "insufficient_evidence" in cat:
                    insufficient_evidence_count += 1
                elif "llm_provider" in cat:
                    llm_provider_errors += 1
                elif "embedding" in cat:
                    embedding_provider_errors += 1
                elif "database" in cat:
                    db_errors += 1
                elif "citation" in cat:
                    citation_validation_failure_count += 1

            for sp in tr.spans:
                st = sp.step_type.lower()
                dur = sp.duration_ms
                stage_totals[st] = stage_totals.get(st, 0.0) + dur
                stage_counts[st] = stage_counts.get(st, 0) + 1

                if st in ("retrieval", "hybrid_retrieval", "dense_retrieval"):
                    retrieval_durations.append(dur)
                    if sp.outputs.get("returned_count") == 0 or sp.outputs.get("retrieved_chunks") == 0:
                        empty_retrieval_count += 1
                elif st in ("rerank", "reranking"):
                    rerank_durations.append(dur)
                elif st in ("llm", "generation", "grounded_generation"):
                    generation_durations.append(dur)
                elif st in ("citation_validation", "citations"):
                    citation_durations.append(dur)
                    if sp.status == "failed" or sp.outputs.get("citation_validation_passed") is False:
                        citation_validation_failure_count += 1
                elif st in ("recovery", "self_healing", "bounded_retry"):
                    recovery_durations.append(dur)

        durations.sort()
        avg_lat = round(sum(durations) / len(durations), 2) if durations else None

        # Safely compute percentiles only when sample size threshold is met
        p50 = None
        p95 = None
        p99 = None
        if len(durations) >= cls.MIN_PERCENTILE_SAMPLE_SIZE:
            p50 = compute_percentile(durations, 50.0)
            p95 = compute_percentile(durations, 95.0)
            p99 = compute_percentile(durations, 99.0)

        def avg_or_none(values: list[float]) -> float | None:
            return round(sum(values) / len(values), 2) if values else None

        stage_breakdown = {
            st: round(stage_totals[st] / stage_counts[st], 2) for st in stage_totals if stage_counts.get(st, 0) > 0
        }

        error_rate = round(failed / total, 4) if total > 0 else 0.0
        completion_rate = round(successful / total, 4) if total > 0 else 0.0
        failure_rate = round(failed / total, 4) if total > 0 else 0.0

        return ReliabilityMetrics(
            total_requests=total,
            successful_requests=successful,
            failed_requests=failed,
            recovered_requests=recovered,
            error_rate=error_rate,
            avg_latency_ms=avg_lat,
            p50_latency_ms=p50,
            p95_latency_ms=p95,
            p99_latency_ms=p99,
            retrieval_latency_ms=avg_or_none(retrieval_durations),
            reranking_latency_ms=avg_or_none(rerank_durations),
            generation_latency_ms=avg_or_none(generation_durations),
            citation_validation_latency_ms=avg_or_none(citation_durations),
            recovery_latency_ms=avg_or_none(recovery_durations),
            timeout_count=timeout_count,
            retry_count=total_retries,
            insufficient_evidence_count=insufficient_evidence_count,
            empty_retrieval_count=empty_retrieval_count,
            citation_validation_failure_count=citation_validation_failure_count,
            workflow_completion_rate=completion_rate,
            workflow_failure_rate=failure_rate,
            llm_provider_error_count=llm_provider_errors,
            embedding_provider_error_count=embedding_provider_errors,
            database_error_count=db_errors,
            stage_breakdown=stage_breakdown,
        )
