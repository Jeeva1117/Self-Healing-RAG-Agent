"""System metadata schemas."""

from pydantic import BaseModel, Field


class SystemInfoResponse(BaseModel):
    service: str = Field(..., description="Service identifier name")
    version: str = Field(..., description="Semantic version")
    environment: str = Field(..., description="Active environment (development, production, etc.)")
    python_version: str = Field(..., description="Runtime Python version")
    features: dict[str, bool] = Field(..., description="Current status of feature subsystems")
