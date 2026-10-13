"""PostgreSQL relational database connector with safe schema discovery and SQL injection protection."""

import re
from typing import Any
from urllib.parse import urlparse

import asyncpg

from app.core.config import settings
from app.core.logging import get_logger
from app.services.connectors.base import (
    BaseConnector,
    ConnectionTestResult,
    NormalizedDocument,
    SourceItem,
)

logger = get_logger(__name__)

# Valid SQL identifier regex (alphanumeric and underscores only)
SQL_IDENTIFIER_PATTERN = re.compile(r"^[a-zA-Z_][a-zA-Z0-9_]*$")

# Sensitive columns excluded by default from indexing
EXCLUDED_COLUMN_PATTERNS = {
    "password", "passwd", "pwd", "hash", "secret", "token", "auth_token",
    "access_token", "private_key", "ssn", "credit_card", "cvv",
}


class PostgreSQLConnector(BaseConnector):
    """Safely extracts structured records from external PostgreSQL relational databases."""

    def __init__(self, config: dict[str, Any]):
        super().__init__(config)
        self.host = (config.get("host") or "127.0.0.1").strip()
        self.port = int(config.get("port") or 5432)
        self.database = (config.get("database") or "").strip()
        self.user = (config.get("user") or config.get("username") or "").strip()
        self.password = (config.get("password") or "").strip()
        self.schema = (config.get("schema") or "public").strip()
        self.max_rows = min(int(config.get("max_rows", 50)), 500)
        self.allow_self_connect = bool(config.get("allow_self_connect", False))

    def _is_self_connection(self) -> bool:
        """Detects if connection targets the application's internal database."""
        try:
            app_db_url = settings.DATABASE_URL
            parsed = urlparse(app_db_url)
            app_host = parsed.hostname or "127.0.0.1"
            app_port = parsed.port or 5432
            app_db = parsed.path.strip("/")

            is_same_host = self.host in ("127.0.0.1", "localhost", app_host)
            is_same_port = self.port == app_port
            is_same_db = self.database == app_db

            return is_same_host and is_same_port and is_same_db
        except Exception:
            return False

    @staticmethod
    def is_sensitive_column(column_name: str) -> bool:
        """Determines if a database column contains credentials, tokens, or sensitive PII."""
        col_lower = column_name.lower()
        return any(pattern in col_lower for pattern in EXCLUDED_COLUMN_PATTERNS)

    async def _get_connection(self, timeout: float = 5.0) -> asyncpg.Connection:
        return await asyncpg.connect(
            host=self.host,
            port=self.port,
            database=self.database,
            user=self.user,
            password=self.password,
            timeout=timeout,
            command_timeout=timeout,
        )

    async def test_connection(self) -> ConnectionTestResult:
        if not self.database or not self.user:
            return ConnectionTestResult(
                success=False,
                message="Database name and Username are required.",
                can_browse=False,
            )

        # Check self-connection safeguard
        if self._is_self_connection() and not self.allow_self_connect:
            return ConnectionTestResult(
                success=False,
                message="Security Safeguard: Connecting to the application's internal database as an external data source is blocked by default.",
                details={"self_connection_detected": True},
                can_browse=False,
            )

        try:
            conn = await self._get_connection(timeout=5.0)
            try:
                version = await conn.fetchval("SELECT version()")
                table_count = await conn.fetchval(
                    "SELECT count(*) FROM information_schema.tables WHERE table_schema = $1 AND table_type = 'BASE TABLE'",
                    self.schema,
                )
                return ConnectionTestResult(
                    success=True,
                    message=f"Connected to database '{self.database}' ({table_count} tables found in schema '{self.schema}')",
                    details={
                        "schema": self.schema,
                        "table_count": table_count,
                        "pg_version": version.split(",")[0] if version else "unknown",
                    },
                    can_browse=True,
                )
            finally:
                await conn.close()
        except Exception as e:
            return ConnectionTestResult(
                success=False,
                message=f"PostgreSQL connection failed: {str(e)}",
                can_browse=False,
            )

    async def list_sources(self, parent_id: str | None = None) -> list[SourceItem]:
        """Discovers tables in the specified schema."""
        if not self.database or not self.user:
            return []

        if self._is_self_connection() and not self.allow_self_connect:
            return []

        items: list[SourceItem] = []
        try:
            conn = await self._get_connection(timeout=5.0)
            try:
                query = """
                    SELECT table_name
                    FROM information_schema.tables
                    WHERE table_schema = $1 AND table_type = 'BASE TABLE'
                    ORDER BY table_name
                """
                rows = await conn.fetch(query, self.schema)
                for r in rows:
                    t_name = r["table_name"]
                    items.append(
                        SourceItem(
                            id=t_name,
                            name=t_name,
                            item_type="table",
                            metadata={"schema": self.schema, "table": t_name},
                        )
                    )
            finally:
                await conn.close()
        except Exception as e:
            logger.error(f"Failed to list PostgreSQL tables: {e}")

        return items

    async def extract_content(self, selected_ids: list[str]) -> list[NormalizedDocument]:
        """Queries rows from selected tables and formats into semantic key-value documents."""
        docs: list[NormalizedDocument] = []
        if not selected_ids:
            return docs

        try:
            conn = await self._get_connection(timeout=10.0)
            try:
                for table_name in selected_ids:
                    # Validate identifier against SQL injection
                    if not SQL_IDENTIFIER_PATTERN.match(table_name) or not SQL_IDENTIFIER_PATTERN.match(self.schema):
                        logger.warning(f"Invalid SQL table or schema identifier: {table_name}")
                        continue

                    # Fetch column names
                    col_query = """
                        SELECT column_name, data_type
                        FROM information_schema.columns
                        WHERE table_schema = $1 AND table_name = $2
                        ORDER BY ordinal_position
                    """
                    cols = await conn.fetch(col_query, self.schema, table_name)

                    # Fetch column names, filtering out sensitive secret/credential columns
                    col_names = [
                        c["column_name"]
                        for c in cols
                        if not any(pattern in c["column_name"].lower() for pattern in EXCLUDED_COLUMN_PATTERNS)
                    ]

                    if not col_names:
                        continue

                    # Fetch rows safely using strict quoted identifiers and row limit
                    safe_cols = ", ".join(f'"{c}"' for c in col_names)
                    data_query = f'SELECT {safe_cols} FROM "{self.schema}"."{table_name}" LIMIT $1'
                    data_rows = await conn.fetch(data_query, self.max_rows)

                    if not data_rows:
                        continue

                    # Group rows into batches of 5
                    batch_size = 5
                    for b_start in range(0, len(data_rows), batch_size):
                        batch = data_rows[b_start : b_start + batch_size]
                        text_blocks = [f"Table: {self.schema}.{table_name} (Rows {b_start + 1} to {min(b_start + batch_size, len(data_rows))})"]

                        for r_idx, row in enumerate(batch, start=b_start + 1):
                            row_fields = [f"Row #{r_idx}:"]
                            for col in col_names:
                                val = row[col]
                                val_str = str(val) if val is not None else "NULL"
                                row_fields.append(f"  {col}: {val_str}")
                            text_blocks.append("\n".join(row_fields))

                        combined_text = "\n\n".join(text_blocks)
                        doc_title = f"{table_name} (Rows {b_start + 1}-{min(b_start + batch_size, len(data_rows))})"
                        safe_filename = f"pg_{self.schema}_{table_name}_{b_start + 1}.txt"

                        docs.append(
                            NormalizedDocument(
                                source_id=f"{table_name}:{b_start}",
                                document_id=f"{self.schema}.{table_name}",
                                source_path=f"{self.schema}.{table_name}",
                                title=doc_title,
                                content=combined_text,
                                source_url=f"postgresql://{self.host}:{self.port}/{self.database}?table={self.schema}.{table_name}",
                                filename=safe_filename,
                                metadata={
                                    "database": self.database,
                                    "schema": self.schema,
                                    "table": table_name,
                                    "row_range": f"{b_start + 1}-{min(b_start + batch_size, len(data_rows))}",
                                    "source_type": "postgres",
                                },
                            )
                        )
            finally:
                await conn.close()
        except Exception as e:
            logger.error(f"Failed to extract content from PostgreSQL: {e}")

        return docs
