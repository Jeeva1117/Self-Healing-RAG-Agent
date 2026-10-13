"""Base connector interfaces, abstractions, and normalized data contracts."""

from abc import ABC, abstractmethod
from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field


class ConnectionTestResult(BaseModel):
    """Result of validating credentials and connectivity to an external source."""

    success: bool
    message: str
    details: dict[str, Any] = Field(default_factory=dict)
    can_browse: bool = False


class SourceItem(BaseModel):
    """A selectable item from a data source (e.g. file, repo, table, page)."""

    id: str
    name: str
    item_type: str  # "file", "folder", "repository", "table", "page", "url"
    size_bytes: int | None = None
    path: str | None = None
    mime_type: str | None = None
    url: str | None = None
    selectable: bool = True
    metadata: dict[str, Any] = Field(default_factory=dict)


class NormalizedDocument(BaseModel):
    """A standardized extracted document ready for ingestion into the RAG corpus."""

    source_id: str
    document_id: str | None = None
    title: str
    content: str
    source_url: str | None = None
    source_path: str | None = None
    mime_type: str = "text/plain"
    filename: str
    author: str | None = None
    version_tag: str | None = None
    created_at: datetime | None = None
    last_modified: datetime | None = None
    permissions: dict[str, Any] = Field(default_factory=dict)
    metadata: dict[str, Any] = Field(default_factory=dict)


class SyncProgress(BaseModel):
    """Real-time progress reporting during synchronization."""

    current_item: str
    items_completed: int
    items_total: int
    bytes_processed: int = 0
    status: str = "syncing"
    error: str | None = None


class SyncResult(BaseModel):
    """Outcome of synchronizing selected items into a Knowledge Base."""

    success: bool
    source_id: UUID
    knowledge_base_id: UUID
    documents_created: int = 0
    documents_updated: int = 0
    chunks_created: int = 0
    errors: list[str] = Field(default_factory=list)
    synced_items: list[str] = Field(default_factory=list)


class BaseConnector(ABC):
    """Abstract base class for all external data source connectors."""

    def __init__(self, config: dict[str, Any]):
        self.config = config

    def validate_config(self) -> tuple[bool, str]:
        """Validates configuration parameters prior to making external calls."""
        return True, "Configuration valid."

    @abstractmethod
    async def test_connection(self) -> ConnectionTestResult:
        """Validates credentials, permissions, and network connectivity."""
        pass

    @abstractmethod
    async def list_sources(self, parent_id: str | None = None) -> list[SourceItem]:
        """Lists discoverable and selectable source items available for ingestion."""
        pass

    @abstractmethod
    async def extract_content(self, selected_ids: list[str]) -> list[NormalizedDocument]:
        """Extracts content from selected source items into normalized document format."""
        pass

    async def disconnect(self) -> bool:
        """Revokes external sessions, tokens, or connections where supported."""
        return True
