"""Common Pydantic schemas for standard API envelope responses."""

from typing import Any, Generic, TypeVar

from pydantic import BaseModel, Field

DataT = TypeVar("DataT")


class ErrorDetail(BaseModel):
    code: str = Field(..., description="Machine-readable error code")
    message: str = Field(..., description="Human-readable error description")
    details: dict[str, Any] | None = Field(default=None, description="Contextual error details")


class MetaInfo(BaseModel):
    request_id: str | None = Field(default=None, description="Tracing correlation ID")
    timestamp: str = Field(..., description="UTC timestamp in ISO format")
    total: int | None = Field(default=None, description="Total record count for paginated listings")
    offset: int | None = Field(default=None, description="Pagination offset index")
    limit: int | None = Field(default=None, description="Pagination page size limit")


class ApiResponse(BaseModel, Generic[DataT]):
    """Standardized API response wrapper."""

    success: bool = Field(default=True, description="Indicates request success")
    data: DataT | None = Field(default=None, description="Response payload")
    error: ErrorDetail | None = Field(default=None, description="Error detail when success=False")
    meta: MetaInfo | None = Field(default=None, description="Metadata envelope")
