"""In-app reliability alerting engine with threshold evaluation and cooldown protection."""

import time
from datetime import UTC, datetime
from typing import Any

from app.services.observability.schemas import AlertRecord, AlertSeverity, ReliabilityMetrics


class AlertRule:
    """Configurable alert condition evaluated against runtime reliability metrics."""

    def __init__(
        self,
        rule_id: str,
        name: str,
        metric_key: str,
        condition: str,  # "gt", "gte", "lt", "lte", "eq"
        threshold: float,
        severity: AlertSeverity = AlertSeverity.WARNING,
        cooldown_seconds: float = 300.0,
        description: str = "",
        min_total_requests: int = 1,
    ):
        self.rule_id = rule_id
        self.name = name
        self.metric_key = metric_key
        self.condition = condition
        self.threshold = threshold
        self.severity = severity
        self.cooldown_seconds = cooldown_seconds
        self.description = description
        self.min_total_requests = min_total_requests
        self.last_triggered_at: float | None = None

    def evaluate(self, metrics: ReliabilityMetrics, extra_context: dict[str, Any] | None = None) -> AlertRecord | None:
        """Evaluates whether current metrics violate the rule threshold, taking cooldown into account."""
        extra_context = extra_context or {}
        val = getattr(metrics, self.metric_key, None)
        if val is None:
            val = extra_context.get(self.metric_key)

        if val is None:
            return None

        # Guard against noisy alerts when request count is insufficient
        if metrics.total_requests < self.min_total_requests and self.metric_key != "database_error_count":
            return None

        triggered = False
        if self.condition == "gt" and val > self.threshold:
            triggered = True
        elif self.condition == "gte" and val >= self.threshold:
            triggered = True
        elif self.condition == "lt" and val < self.threshold:
            triggered = True
        elif self.condition == "lte" and val <= self.threshold:
            triggered = True
        elif self.condition == "eq" and val == self.threshold:
            triggered = True

        now = time.time()
        if triggered:
            # Check cooldown deduplication
            in_cooldown = self.last_triggered_at is not None and (now - self.last_triggered_at) < self.cooldown_seconds

            status = "cooldown" if in_cooldown else "active"
            if not in_cooldown:
                self.last_triggered_at = now

            formatted_val = f"{val:.1%}" if "rate" in self.metric_key else str(val)
            formatted_threshold = f"{self.threshold:.1%}" if "rate" in self.metric_key else str(self.threshold)

            return AlertRecord(
                id=f"alt-{self.rule_id}",
                name=self.name,
                severity=self.severity.value,
                condition=f"{self.metric_key} {self.condition} {formatted_threshold}",
                threshold=self.threshold,
                current_value=val,
                status=status,
                triggered_at=datetime.now(UTC).isoformat(),
                message=f"{self.name}: Current {formatted_val} violates threshold {formatted_threshold}. {self.description}",
                category="reliability",
            )
        else:
            return None


class AlertManager:
    """Manages active alert rules, evaluations, and state deduplication."""

    def __init__(self):
        self.rules: list[AlertRule] = [
            AlertRule(
                rule_id="elevated_error_rate",
                name="Elevated Pipeline Error Rate",
                metric_key="error_rate",
                condition="gt",
                threshold=0.10,
                severity=AlertSeverity.CRITICAL,
                cooldown_seconds=300.0,
                description="Error rate exceeds 10% tolerance budget.",
                min_total_requests=5,
            ),
            AlertRule(
                rule_id="high_p95_latency",
                name="Sustained High P95 Latency",
                metric_key="p95_latency_ms",
                condition="gt",
                threshold=3500.0,
                severity=AlertSeverity.WARNING,
                cooldown_seconds=300.0,
                description="P95 latency exceeds 3500ms SLA target.",
                min_total_requests=5,
            ),
            AlertRule(
                rule_id="provider_failures",
                name="Repeated LLM Provider Failures",
                metric_key="llm_provider_error_count",
                condition="gte",
                threshold=3.0,
                severity=AlertSeverity.CRITICAL,
                cooldown_seconds=300.0,
                description="Upstream LLM provider has failed 3 or more times.",
                min_total_requests=1,
            ),
            AlertRule(
                rule_id="database_connectivity",
                name="Database Connectivity Errors",
                metric_key="database_error_count",
                condition="gt",
                threshold=0.0,
                severity=AlertSeverity.CRITICAL,
                cooldown_seconds=180.0,
                description="PostgreSQL database queries or connections are failing.",
                min_total_requests=1,
            ),
            AlertRule(
                rule_id="high_timeouts",
                name="Excessive Timeout Count",
                metric_key="timeout_count",
                condition="gte",
                threshold=3.0,
                severity=AlertSeverity.WARNING,
                cooldown_seconds=300.0,
                description="Cumulative stage timeouts have reached threshold.",
                min_total_requests=1,
            ),
            AlertRule(
                rule_id="eval_regression",
                name="Phase 9 Quality Evaluation Regression",
                metric_key="eval_pass_rate",
                condition="lt",
                threshold=0.70,
                severity=AlertSeverity.WARNING,
                cooldown_seconds=300.0,
                description="Evaluation suite pass rate dropped below 70%.",
                min_total_requests=1,
            ),
        ]
        self._history: list[AlertRecord] = []

    def evaluate(
        self,
        metrics: ReliabilityMetrics,
        extra_context: dict[str, Any] | None = None,
    ) -> list[AlertRecord]:
        """Evaluates all rules against current metrics and retains history."""
        current_alerts: list[AlertRecord] = []
        for rule in self.rules:
            alert = rule.evaluate(metrics, extra_context=extra_context)
            if alert:
                current_alerts.append(alert)
                # Avoid duplicating identical alerts in history
                if not any(h.id == alert.id and h.triggered_at == alert.triggered_at for h in self._history):
                    self._history.insert(0, alert)

        # Cap history to 50 entries
        self._history = self._history[:50]
        return current_alerts

    def get_history(self) -> list[AlertRecord]:
        """Returns chronological list of triggered alerts."""
        return list(self._history)


# Global AlertManager singleton
alert_manager = AlertManager()
