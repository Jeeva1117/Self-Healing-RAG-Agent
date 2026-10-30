"""Pydantic schemas for Document and Chunk endpoints."""

from datetime import datetime
from typing import Any
from uuid import UUID

from app.infrastructure.database.models import DocumentStatus
from pydantic import BaseModel, Field


class DocumentResponse(BaseModel):
    id: UUID
    knowledge_base_id: UUID
    owner_id: UUID
    filename: str
    original_filename: str
    content_type: str
    file_size: int
    checksum: str
    storage_key: str
    status: DocumentStatus
    ingestion_error: str | None = None
    created_at: datetime
    updated_at: datetime
    chunk_count: int = 0
    active_version: int = 1

    model_config = {"from_attributes": True}


class DocumentListResponse(BaseModel):
    items: list[DocumentResponse]
    total: int
    limit: int
    offset: int


class DocumentChunkResponse(BaseModel):
    id: UUID
    document_id: UUID
    document_version_id: UUID
    chunk_index: int
    content: str
    token_count: int | None = None
    character_count: int
    page_number: int | None = None
    section_title: str | None = None
    start_offset: int | None = None
    end_offset: int | None = None
    metadata_json: dict[str, Any] = Field(default_factory=dict, alias="chunk_metadata")
    created_at: datetime

    model_config = {"from_attributes": True, "populate_by_name": True}


class DocumentChunkListResponse(BaseModel):
    items: list[DocumentChunkResponse]
    total: int
    limit: int
    offset: int


class ReprocessResponse(BaseModel):
    document_id: UUID
    status: DocumentStatus
    message: str
