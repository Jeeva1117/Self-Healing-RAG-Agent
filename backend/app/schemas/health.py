"""Health check request and response schemas."""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class DependencyHealth(BaseModel):
    status: str = Field(..., description="'healthy', 'unhealthy', or 'degraded'")
    connected: bool = Field(..., description="Whether a live connection was established")
    latency_ms: float | None = Field(default=None, description="Roundtrip check latency in milliseconds")
    details: dict[str, Any] | None = Field(default=None, description="Optional extra status metadata")


class HealthResponse(BaseModel):
    status: str = Field(default="ok", description="Overall service status")
    service: str = Field(..., description="Service identifier name")
    version: str = Field(..., description="Semantic service version")
    timestamp: datetime = Field(..., description="Current server UTC timestamp")


class LivenessResponse(BaseModel):
    status: str = Field(default="alive", description="Process liveness indicator")
    service: str = Field(..., description="Service identifier")
    uptime_seconds: float = Field(..., description="Seconds since process startup")


class ReadinessResponse(BaseModel):
    status: str = Field(..., description="'ready', 'degraded', or 'not_ready'")
    service: str = Field(..., description="Service identifier")
    ready: bool = Field(..., description="Whether service is ready to accept production traffic")
    dependencies: dict[str, DependencyHealth] = Field(..., description="Health status of downstream dependencies")
