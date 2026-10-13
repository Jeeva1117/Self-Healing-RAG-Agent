"""Schemas for Data Sources and External Connectors."""

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field


def mask_sensitive_config(config: dict[str, Any]) -> dict[str, Any]:
    """Masks API keys, passwords, and tokens before sending config to client."""
    masked: dict[str, Any] = {}
    sensitive_keys = {
        "password",
        "token",
        "secret",
        "api_key",
        "access_token",
        "refresh_token",
        "client_secret",
        "personal_access_token",
    }
    for k, v in config.items():
        if any(s in k.lower() for s in sensitive_keys) and isinstance(v, str) and len(v) > 0:
            if len(v) > 8:
                masked[k] = f"{v[:4]}...{v[-4:]}"
            else:
                masked[k] = "******"
        else:
            masked[k] = v
    return masked


class DataSourceCreateRequest(BaseModel):
    """Payload to create or configure a data source connector."""

    source_type: str = Field(..., description="One of: web, github, gdrive, notion, postgres")
    name: str = Field(..., min_length=1, max_length=150)
    description: str | None = Field(default=None, max_length=500)
    knowledge_base_id: UUID | None = Field(default=None, description="Optional default KB target")
    config: dict[str, Any] = Field(default_factory=dict, description="Connector-specific configuration")


class DataSourceUpdateRequest(BaseModel):
    """Payload to update an existing data source configuration."""

    name: str | None = Field(default=None, min_length=1, max_length=150)
    description: str | None = Field(default=None, max_length=500)
    knowledge_base_id: UUID | None = None
    config: dict[str, Any] | None = None


class DataSourceResponse(BaseModel):
    """Response representing a configured data source."""

    id: UUID
    user_id: UUID
    knowledge_base_id: UUID | None = None
    source_type: str
    name: str
    description: str | None = None
    config: dict[str, Any]
    status: str
    last_sync_at: datetime | None = None
    last_sync_status: str | None = None
    last_sync_error: str | None = None
    synced_documents_count: int = 0
    synced_chunks_count: int = 0
    created_at: datetime
    updated_at: datetime


class ConnectionTestResponse(BaseModel):
    """Result of connection or credential testing."""

    success: bool
    message: str
    details: dict[str, Any] = Field(default_factory=dict)
    can_browse: bool = False


class SourceItemResponse(BaseModel):
    """An item discoverable from the data source (repo, file, table, page)."""

    id: str
    name: str
    item_type: str
    size_bytes: int | None = None
    path: str | None = None
    mime_type: str | None = None
    url: str | None = None
    selectable: bool = True
    metadata: dict[str, Any] = Field(default_factory=dict)


class SyncRequest(BaseModel):
    """Payload to initiate synchronization into a knowledge base."""

    selected_ids: list[str] = Field(..., min_length=1, description="List of source item IDs to sync")
    knowledge_base_id: UUID | None = Field(default=None, description="Target Knowledge Base ID")


class SyncResponse(BaseModel):
    """Outcome of synchronization."""

    success: bool
    source_id: UUID
    knowledge_base_id: UUID
    documents_created: int = 0
    documents_updated: int = 0
    chunks_created: int = 0
    errors: list[str] = Field(default_factory=list)
    synced_items: list[str] = Field(default_factory=list)


class ConnectorCatalogItem(BaseModel):
    """Metadata describing a connector type for display in the UI catalog."""

    source_type: str
    name: str
    description: str
    icon: str
    requires_auth: bool
    auth_type: str
    configured_count: int = 0
    active_status: str = "not_configured"
    setup_guide: str = ""
