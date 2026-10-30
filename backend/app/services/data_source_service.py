"""Service managing external data sources, connector lifecycle, testing, and synchronization."""

import hashlib
from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import AppError
from app.core.logging import get_logger
from app.infrastructure.database.models import (
    DataSource,
    DataSourceStatus,
    DataSourceType,
    DocumentStatus,
)
from app.repositories.data_source_repository import DataSourceRepository
from app.repositories.document_repository import DocumentRepository
from app.repositories.knowledge_base_repository import KnowledgeBaseRepository
from app.schemas.data_source import (
    ConnectionTestResponse,
    ConnectorCatalogItem,
    DataSourceCreateRequest,
    DataSourceResponse,
    DataSourceUpdateRequest,
    SourceItemResponse,
    SyncRequest,
    SyncResponse,
    mask_sensitive_config,
)
from app.services.connectors.base import BaseConnector, ConnectionTestResult, SourceItem
from app.services.connectors.gdrive_connector import GoogleDriveConnector
from app.services.connectors.github_connector import GitHubConnector
from app.services.connectors.notion_connector import NotionConnector
from app.services.connectors.postgres_connector import PostgreSQLConnector
from app.services.connectors.web_scraper import WebScraperConnector
from app.services.ingestion_service import IngestionService

logger = get_logger(__name__)


class DataSourceService:
    """Coordinates data source configurations, connector execution, and corpus synchronization."""

    def __init__(self, session: AsyncSession, ingestion_service: IngestionService | None = None):
        self.session = session
        self.ds_repo = DataSourceRepository(session)
        self.kb_repo = KnowledgeBaseRepository(session)
        self.doc_repo = DocumentRepository(session)
        self.ingestion_service = ingestion_service or IngestionService(session)

    @staticmethod
    def get_connector(source_type: str, config: dict[str, Any]) -> BaseConnector:
        """Instantiates the specialized connector implementation based on source type."""
        st = source_type.lower().strip()
        if st in (DataSourceType.WEB.value, "web", "website", "documentation"):
            return WebScraperConnector(config)
        elif st in (DataSourceType.GITHUB.value, "github", "git"):
            return GitHubConnector(config)
        elif st in (DataSourceType.GDRIVE.value, "gdrive", "google_drive", "drive"):
            return GoogleDriveConnector(config)
        elif st in (DataSourceType.NOTION.value, "notion"):
            return NotionConnector(config)
        elif st in (DataSourceType.POSTGRES.value, "postgres", "postgresql", "relational"):
            return PostgreSQLConnector(config)
        else:
            raise AppError(
                code="UNSUPPORTED_DATA_SOURCE_TYPE",
                message=f"Connector type '{source_type}' is not supported.",
                status_code=400,
            )

    async def get_catalog(self, user_id: UUID) -> list[ConnectorCatalogItem]:
        """Provides metadata for all supported connectors and user-specific configuration status."""
        user_sources, _ = await self.ds_repo.list_by_user(user_id)
        source_map: dict[str, list[DataSource]] = {}
        for s in user_sources:
            source_map.setdefault(s.source_type, []).append(s)

        catalog_definitions = [
            {
                "source_type": DataSourceType.LOCAL.value,
                "name": "Local Files & Manual Upload",
                "description": "Upload PDF, DOCX, TXT, Markdown, CSV, HTML, JSON, and XLSX files directly into the Knowledge Base.",
                "icon": "FolderUp",
                "requires_auth": False,
                "auth_type": "none",
                "setup_guide": "Supported directly via the Knowledge Base upload section.",
            },
            {
                "source_type": DataSourceType.WEB.value,
                "name": "Website & Documentation Scraper",
                "description": "Crawl public documentation, blogs, and websites with SSRF protection, robots.txt compliance, and rate limiting.",
                "icon": "Globe",
                "requires_auth": False,
                "auth_type": "none",
                "setup_guide": "Provide a valid public root URL (e.g. https://docs.python.org/3/). Private networks and localhost are blocked.",
            },
            {
                "source_type": DataSourceType.GITHUB.value,
                "name": "GitHub Repositories",
                "description": "Index repositories, documentation, and source code. Automatically excludes secrets (.env, keys) and binaries.",
                "icon": "GitFork",
                "requires_auth": True,
                "auth_type": "pat",
                "setup_guide": "Generate a GitHub Personal Access Token (classic or fine-grained) with 'repo' read access and specify the repository.",
            },
            {
                "source_type": DataSourceType.GDRIVE.value,
                "name": "Google Drive",
                "description": "Browse and ingest Google Docs, PDFs, and folders with OAuth or service credentials.",
                "icon": "HardDrive",
                "requires_auth": True,
                "auth_type": "oauth",
                "setup_guide": "Set up a Google Cloud OAuth Client ID or Service Account key with the 'https://www.googleapis.com/auth/drive.readonly' scope.",
            },
            {
                "source_type": DataSourceType.NOTION.value,
                "name": "Notion Workspaces",
                "description": "Sync workspace pages and databases into structured markdown using the official Notion API.",
                "icon": "BookOpen",
                "requires_auth": True,
                "auth_type": "token",
                "setup_guide": "Create an internal Notion integration at notion.so/my-integrations, copy the secret token, and share target pages with the integration.",
            },
            {
                "source_type": DataSourceType.POSTGRES.value,
                "name": "PostgreSQL Relational Tables",
                "description": "Securely connect read-only PostgreSQL databases to index approved tables and schemas.",
                "icon": "Database",
                "requires_auth": True,
                "auth_type": "connection_string",
                "setup_guide": "Provide host, port, database, read-only user credentials. Internal application databases are blocked by default.",
            },
        ]

        catalog: list[ConnectorCatalogItem] = []
        for defn in catalog_definitions:
            st = defn["source_type"]
            configured = source_map.get(st, [])
            status = DataSourceStatus.NOT_CONFIGURED.value
            if st == DataSourceType.LOCAL.value:
                status = DataSourceStatus.READY.value
            elif configured:
                status = configured[0].status

            catalog.append(
                ConnectorCatalogItem(
                    source_type=st,
                    name=defn["name"],
                    description=defn["description"],
                    icon=defn["icon"],
                    requires_auth=defn["requires_auth"],
                    auth_type=defn["auth_type"],
                    configured_count=len(configured),
                    active_status=status,
                    setup_guide=defn["setup_guide"],
                )
            )

        return catalog

    async def create_data_source(self, user_id: UUID, req: DataSourceCreateRequest) -> DataSourceResponse:
        """Configures a new data source connector for the user."""
        if req.knowledge_base_id:
            kb = await self.kb_repo.get_by_id_and_owner(req.knowledge_base_id, user_id)
            if not kb:
                raise AppError(
                    code="KNOWLEDGE_BASE_NOT_FOUND",
                    message="Target knowledge base not found or access denied.",
                    status_code=404,
                )

        initial_status = DataSourceStatus.NOT_CONFIGURED.value
        # For web scraper, if root_url is provided, it can be tested immediately
        if req.source_type == DataSourceType.WEB.value and req.config.get("root_url"):
            initial_status = DataSourceStatus.DISCONNECTED.value
        elif req.config:
            initial_status = DataSourceStatus.DISCONNECTED.value

        ds = DataSource(
            id=uuid4(),
            user_id=user_id,
            knowledge_base_id=req.knowledge_base_id,
            source_type=req.source_type,
            name=req.name,
            description=req.description,
            config=req.config,
            status=initial_status,
        )
        created = await self.ds_repo.create(ds)
        await self.session.commit()
        await self.session.refresh(created)
        return self._to_response(created)

    async def update_data_source(
        self, source_id: UUID, user_id: UUID, req: DataSourceUpdateRequest
    ) -> DataSourceResponse:
        """Updates configuration or metadata for an existing data source."""
        ds = await self.ds_repo.get_by_id_and_user(source_id, user_id)
        if not ds:
            raise AppError(
                code="DATA_SOURCE_NOT_FOUND",
                message="Data source not found or access denied.",
                status_code=404,
            )

        if req.name is not None:
            ds.name = req.name
        if req.description is not None:
            ds.description = req.description
        if req.knowledge_base_id is not None:
            kb = await self.kb_repo.get_by_id_and_owner(req.knowledge_base_id, user_id)
            if not kb:
                raise AppError(
                    code="KNOWLEDGE_BASE_NOT_FOUND",
                    message="Target knowledge base not found or access denied.",
                    status_code=404,
                )
            ds.knowledge_base_id = req.knowledge_base_id

        if req.config is not None:
            # Preserve existing sensitive fields if client submitted masked values
            updated_config = dict(ds.config or {})
            for k, v in req.config.items():
                if isinstance(v, str) and "..." in v and k in updated_config:
                    continue  # Keep existing unmasked secret
                updated_config[k] = v
            ds.config = updated_config
            ds.status = DataSourceStatus.DISCONNECTED.value

        await self.session.commit()
        await self.session.refresh(ds)
        return self._to_response(ds)

    async def get_data_source(self, source_id: UUID, user_id: UUID) -> DataSourceResponse:
        """Retrieves single data source with masked credentials."""
        ds = await self.ds_repo.get_by_id_and_user(source_id, user_id)
        if not ds:
            raise AppError(
                code="DATA_SOURCE_NOT_FOUND",
                message="Data source not found or access denied.",
                status_code=404,
            )
        return self._to_response(ds)

    async def list_data_sources(
        self, user_id: UUID, source_type: str | None = None, offset: int = 0, limit: int = 50
    ) -> tuple[list[DataSourceResponse], int]:
        """Lists user's configured data sources."""
        sources, total = await self.ds_repo.list_by_user(user_id, source_type=source_type, offset=offset, limit=limit)
        return [self._to_response(s) for s in sources], total

    async def delete_data_source(self, source_id: UUID, user_id: UUID) -> None:
        """Deletes data source configuration and disconnects connector."""
        ds = await self.ds_repo.get_by_id_and_user(source_id, user_id)
        if not ds:
            raise AppError(
                code="DATA_SOURCE_NOT_FOUND",
                message="Data source not found or access denied.",
                status_code=404,
            )
        await self.ds_repo.delete(ds)
        await self.session.commit()
        logger.info("Deleted data source %s (type: %s)", source_id, ds.source_type)

    async def test_connection(
        self, source_id: UUID, user_id: UUID, config_override: dict[str, Any] | None = None
    ) -> ConnectionTestResponse:
        """Validates network connectivity and credentials with external provider."""
        ds = await self.ds_repo.get_by_id_and_user(source_id, user_id)
        if not ds:
            raise AppError(
                code="DATA_SOURCE_NOT_FOUND",
                message="Data source not found or access denied.",
                status_code=404,
            )

        test_config = dict(ds.config or {})
        if config_override:
            test_config.update(config_override)

        connector = self.get_connector(ds.source_type, test_config)
        test_res: ConnectionTestResult = await connector.test_connection()

        if test_res.success:
            ds.status = DataSourceStatus.CONNECTED.value
            ds.last_sync_error = None
        else:
            msg = test_res.message.lower()
            if "setup" in msg or "missing" in msg or "prerequisite" in msg or "not configured" in msg:
                ds.status = DataSourceStatus.SETUP_REQUIRED.value
            else:
                ds.status = DataSourceStatus.FAILED.value
            ds.last_sync_error = test_res.message[:1000]

        await self.session.commit()

        return ConnectionTestResponse(
            success=test_res.success,
            message=test_res.message,
            details=test_res.details,
            can_browse=test_res.can_browse,
        )

    async def list_source_items(
        self, source_id: UUID, user_id: UUID, parent_id: str | None = None
    ) -> list[SourceItemResponse]:
        """Discovers browseable and selectable source items available for synchronization."""
        ds = await self.ds_repo.get_by_id_and_user(source_id, user_id)
        if not ds:
            raise AppError(
                code="DATA_SOURCE_NOT_FOUND",
                message="Data source not found or access denied.",
                status_code=404,
            )

        connector = self.get_connector(ds.source_type, ds.config)
        items: list[SourceItem] = await connector.list_sources(parent_id)

        return [
            SourceItemResponse(
                id=item.id,
                name=item.name,
                item_type=item.item_type,
                size_bytes=item.size_bytes,
                path=item.path,
                mime_type=item.mime_type,
                url=item.url,
                selectable=item.selectable,
                metadata=item.metadata,
            )
            for item in items
        ]

    async def sync_data_source(self, source_id: UUID, user_id: UUID, req: SyncRequest) -> SyncResponse:
        """Executes full extraction, normalization, chunking, and vector embedding into target KB."""
        ds = await self.ds_repo.get_by_id_and_user(source_id, user_id)
        if not ds:
            raise AppError(
                code="DATA_SOURCE_NOT_FOUND",
                message="Data source not found or access denied.",
                status_code=404,
            )

        target_kb_id = req.knowledge_base_id or ds.knowledge_base_id
        if not target_kb_id:
            # Look up first active knowledge base owned by user
            kbs, total = await self.kb_repo.list_by_owner(user_id, limit=1)
            if kbs:
                target_kb_id = kbs[0].id
            else:
                raise AppError(
                    code="TARGET_KNOWLEDGE_BASE_REQUIRED",
                    message="A Knowledge Base is required to ingest data source documents. Please select or create one.",
                    status_code=400,
                )

        kb = await self.kb_repo.get_by_id_and_owner(target_kb_id, user_id)
        if not kb:
            raise AppError(
                code="KNOWLEDGE_BASE_NOT_FOUND",
                message="Target Knowledge Base not found or access denied.",
                status_code=404,
            )

        # Mark source as SYNCING
        ds.status = DataSourceStatus.SYNCING.value
        ds.last_sync_error = None
        await self.session.commit()

        connector = self.get_connector(ds.source_type, ds.config)
        docs_created = 0
        docs_updated = 0
        chunks_created = 0
        errors: list[str] = []
        synced_items: list[str] = []

        try:
            # 1. Extract content from connector
            extracted_docs = await connector.extract_content(req.selected_ids)
            if not extracted_docs:
                ds.status = DataSourceStatus.CONNECTED.value
                ds.last_sync_at = datetime.now(UTC)
                ds.last_sync_status = "empty"
                await self.session.commit()
                return SyncResponse(
                    success=True,
                    source_id=source_id,
                    knowledge_base_id=target_kb_id,
                    documents_created=0,
                    documents_updated=0,
                    chunks_created=0,
                    errors=["No documents were extractable from the selected items."],
                    synced_items=[],
                )

            # 2. Ingest through standard pipeline
            for norm_doc in extracted_docs:
                try:
                    file_bytes = norm_doc.content.encode("utf-8")
                    if not file_bytes:
                        continue

                    checksum = hashlib.sha256(file_bytes).hexdigest()
                    existing_doc = await self.doc_repo.get_by_checksum_and_kb(target_kb_id, checksum)

                    if existing_doc and existing_doc.status != DocumentStatus.DELETED:
                        # Document with same content is already indexed and ready
                        docs_updated += 1
                        synced_items.append(norm_doc.title)
                        continue

                    doc_meta = {
                        "source_id": str(source_id),
                        "source_type": ds.source_type,
                        "source_name": ds.name,
                        "source_url": norm_doc.source_url,
                        "title": norm_doc.title,
                        **norm_doc.metadata,
                    }

                    # Determine filename with valid extension
                    fname = norm_doc.filename
                    if not any(
                        fname.lower().endswith(f".{ext}") for ext in ["md", "txt", "html", "htm", "json", "csv"]
                    ):
                        fname = f"{fname}.md"

                    created_doc = await self.ingestion_service.validate_and_create_document(
                        kb_id=target_kb_id,
                        user_id=user_id,
                        filename=fname,
                        content_type=norm_doc.mime_type,
                        file_bytes=file_bytes,
                        document_metadata=doc_meta,
                    )

                    await self.ingestion_service.run_ingestion_pipeline(created_doc.id)

                    chunk_count = await self.doc_repo.get_chunk_count(created_doc.id)
                    chunks_created += chunk_count
                    docs_created += 1
                    synced_items.append(norm_doc.title)

                except Exception as doc_err:
                    err_msg = f"Failed to ingest '{norm_doc.title}': {str(doc_err)}"
                    logger.warning(err_msg, exc_info=True)
                    errors.append(err_msg)

            # Update final source status
            ds.last_sync_at = datetime.now(UTC)
            ds.synced_documents_count += docs_created
            ds.synced_chunks_count += chunks_created

            if docs_created > 0 or docs_updated > 0:
                ds.status = DataSourceStatus.READY.value if not errors else DataSourceStatus.PARTIAL_FAILURE.value
                ds.last_sync_status = "success" if not errors else "partial"
            else:
                ds.status = DataSourceStatus.FAILED.value
                ds.last_sync_status = "failed"
                ds.last_sync_error = errors[0] if errors else "No documents could be synced."

            await self.session.commit()

            return SyncResponse(
                success=len(errors) == 0,
                source_id=source_id,
                knowledge_base_id=target_kb_id,
                documents_created=docs_created,
                documents_updated=docs_updated,
                chunks_created=chunks_created,
                errors=errors,
                synced_items=synced_items,
            )

        except Exception as sync_err:
            logger.error("Data source sync failed: %s", sync_err, exc_info=True)
            ds.status = DataSourceStatus.FAILED.value
            ds.last_sync_status = "failed"
            ds.last_sync_error = str(sync_err)[:1000]
            await self.session.commit()
            raise AppError(
                code="SYNC_FAILED",
                message=f"Synchronization failed: {str(sync_err)}",
                status_code=500,
            ) from sync_err

    @staticmethod
    def _to_response(ds: DataSource) -> DataSourceResponse:
        """Converts database model into sanitized response with masked credentials."""
        return DataSourceResponse(
            id=ds.id,
            user_id=ds.user_id,
            knowledge_base_id=ds.knowledge_base_id,
            source_type=ds.source_type,
            name=ds.name,
            description=ds.description,
            config=mask_sensitive_config(ds.config or {}),
            status=ds.status,
            last_sync_at=ds.last_sync_at,
            last_sync_status=ds.last_sync_status,
            last_sync_error=ds.last_sync_error,
            synced_documents_count=ds.synced_documents_count,
            synced_chunks_count=ds.synced_chunks_count,
            created_at=ds.created_at,
            updated_at=ds.updated_at,
        )
