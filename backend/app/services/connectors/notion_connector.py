"""Notion workspace connector using official Notion v1 REST API."""

from typing import Any

import httpx

from app.core.logging import get_logger
from app.services.connectors.base import (
    BaseConnector,
    ConnectionTestResult,
    NormalizedDocument,
    SourceItem,
)

logger = get_logger(__name__)


def _extract_rich_text(rich_text_list: list[dict[str, Any]]) -> str:
    """Combines text elements from Notion rich_text blocks."""
    return "".join(t.get("plain_text", "") for t in rich_text_list).strip()


class NotionConnector(BaseConnector):
    """Integrates with Notion workspaces to index internal pages and wikis."""

    def __init__(self, config: dict[str, Any]):
        super().__init__(config)
        self.api_key = (
            config.get("integration_token")
            or config.get("api_key")
            or config.get("token")
            or config.get("notion_secret")
            or ""
        ).strip()
        self.api_base = "https://api.notion.com/v1"
        self.notion_version = "2022-06-28"

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Notion-Version": self.notion_version,
            "Content-Type": "application/json",
        }

    @staticmethod
    def render_blocks_to_text(blocks: list[dict[str, Any]]) -> str:
        """Transforms a collection of Notion block objects into Markdown lines."""
        content_lines: list[str] = []
        for block in blocks:
            b_type = block.get("type")
            if not isinstance(b_type, str):
                continue
            b_data = block.get(b_type)
            if not isinstance(b_data, dict):
                b_data = {}
            rich_text = b_data.get("rich_text", [])
            text = _extract_rich_text(rich_text)

            if b_type == "paragraph":
                if text:
                    content_lines.append(f"{text}\n")
            elif b_type == "heading_1":
                content_lines.append(f"\n# {text}\n")
            elif b_type == "heading_2":
                content_lines.append(f"\n## {text}\n")
            elif b_type == "heading_3":
                content_lines.append(f"\n### {text}\n")
            elif b_type in ("bulleted_list_item", "numbered_list_item"):
                content_lines.append(f"- {text}")
            elif b_type == "to_do":
                checked = b_data.get("checked", False)
                content_lines.append(f"- [{'x' if checked else ' '}] {text}")
            elif b_type == "code":
                lang = b_data.get("language", "")
                content_lines.append(f"\n```{lang}\n{text}\n```\n")
            elif b_type == "callout":
                content_lines.append(f"> 💡 {text}\n")
            elif b_type == "quote":
                content_lines.append(f"> {text}\n")
        return "\n".join(content_lines)

    async def test_connection(self) -> ConnectionTestResult:
        if not self.api_key:
            return ConnectionTestResult(
                success=False,
                message="Setup Required: Notion Internal Integration Token is required (configure at https://www.notion.so/my-integrations).",
                details={
                    "setup_instruction": (
                        "Create an Internal Integration at https://www.notion.so/my-integrations. "
                        "Copy the 'Internal Integration Secret' and share your target Notion pages with the integration via the page '...' menu -> Add Connections."
                    )
                },
                can_browse=False,
            )

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                url = f"{self.api_base}/users/me"
                resp = await client.get(url, headers=self._headers())

                if resp.status_code == 200:
                    bot_data = resp.json()
                    bot_name = bot_data.get("name", "Notion Bot")
                    workspace_name = bot_data.get("bot", {}).get("workspace_name", "Workspace")
                    return ConnectionTestResult(
                        success=True,
                        message=f"Connected to Notion workspace '{workspace_name}' as integration @{bot_name}",
                        details={"bot_name": bot_name, "workspace": workspace_name},
                        can_browse=True,
                    )
                elif resp.status_code == 401:
                    return ConnectionTestResult(
                        success=False,
                        message="Invalid Notion integration token. Please check your Secret key.",
                        can_browse=False,
                    )
                else:
                    return ConnectionTestResult(
                        success=False,
                        message=f"Notion API error (HTTP {resp.status_code}): {resp.text}",
                        can_browse=False,
                    )
        except Exception as e:
            return ConnectionTestResult(
                success=False,
                message=f"Failed to connect to Notion: {str(e)}",
                can_browse=False,
            )

    async def list_sources(self, parent_id: str | None = None) -> list[SourceItem]:
        """Searches and lists accessible Notion pages and databases."""
        if not self.api_key:
            return []

        items: list[SourceItem] = []
        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                url = f"{self.api_base}/search"
                payload = {"page_size": 50, "sort": {"direction": "descending", "timestamp": "last_edited_time"}}
                resp = await client.post(url, headers=self._headers(), json=payload)
                if resp.status_code != 200:
                    return []

                results = resp.json().get("results", [])
                for r in results:
                    obj_type = r.get("object", "page")
                    item_id = r.get("id")

                    # Extract title
                    title = "Untitled"
                    if obj_type == "page":
                        properties = r.get("properties", {})
                        for prop in properties.values():
                            if prop.get("type") == "title":
                                title = _extract_rich_text(prop.get("title", [])) or "Untitled"
                                break
                    elif obj_type == "database":
                        title = _extract_rich_text(r.get("title", [])) or "Database"

                    items.append(
                        SourceItem(
                            id=item_id,
                            name=title,
                            item_type=obj_type,
                            url=r.get("url"),
                            metadata={
                                "last_edited_time": r.get("last_edited_time"),
                                "created_time": r.get("created_time"),
                            },
                        )
                    )
        except Exception as e:
            logger.error(f"Failed to list Notion pages: {e}")

        return items

    async def extract_content(self, selected_ids: list[str]) -> list[NormalizedDocument]:
        """Traverses page blocks and formats page content into readable markdown text."""
        docs: list[NormalizedDocument] = []

        async with httpx.AsyncClient(timeout=20.0) as client:
            for page_id in selected_ids:
                try:
                    # Get page metadata
                    page_url = f"{self.api_base}/pages/{page_id}"
                    page_resp = await client.get(page_url, headers=self._headers())
                    # If page fetch failed with 404, check if ID corresponds to a database
                    if page_resp.status_code == 404:
                        db_url = f"{self.api_base}/databases/{page_id}"
                        db_resp = await client.get(db_url, headers=self._headers())
                        if db_resp.status_code == 200:
                            db_data = db_resp.json()
                            db_title = _extract_rich_text(db_data.get("title", [])) or "Database"
                            query_url = f"{self.api_base}/databases/{page_id}/query"
                            query_resp = await client.post(query_url, headers=self._headers(), json={"page_size": 25})
                            if query_resp.status_code == 200:
                                db_rows = query_resp.json().get("results", [])
                                md_lines = [f"# {db_title}\n"]
                                for r_idx, row in enumerate(db_rows, start=1):
                                    row_props = []
                                    for prop_name, prop_val in row.get("properties", {}).items():
                                        p_type = prop_val.get("type")
                                        if p_type == "title":
                                            row_props.append(f"{prop_name}: {_extract_rich_text(prop_val.get('title', []))}")
                                        elif p_type == "rich_text":
                                            row_props.append(f"{prop_name}: {_extract_rich_text(prop_val.get('rich_text', []))}")
                                        elif p_type == "select" and prop_val.get("select"):
                                            row_props.append(f"{prop_name}: {prop_val['select'].get('name')}")
                                    if row_props:
                                        md_lines.append(f"Row #{r_idx}: " + " | ".join(row_props))
                                full_db_text = "\n".join(md_lines).strip()
                                if full_db_text:
                                    safe_db_title = db_title.replace("/", "_")
                                    docs.append(
                                        NormalizedDocument(
                                            source_id=page_id,
                                            document_id=page_id,
                                            title=db_title,
                                            content=full_db_text,
                                            source_url=db_data.get("url"),
                                            filename=f"notion_db_{safe_db_title}.md",
                                            mime_type="text/markdown",
                                            version_tag=db_data.get("last_edited_time"),
                                            metadata={
                                                "notion_database_id": page_id,
                                                "source_type": "notion",
                                                "url": db_data.get("url"),
                                            },
                                        )
                                    )
                        continue

                    if page_resp.status_code != 200:
                        continue

                    page_data = page_resp.json()
                    page_web_url = page_data.get("url")
                    title = "Untitled"
                    for prop in page_data.get("properties", {}).values():
                        if prop.get("type") == "title":
                            title = _extract_rich_text(prop.get("title", [])) or "Untitled"
                            break

                    # Retrieve children blocks with pagination
                    blocks = []
                    start_cursor = None
                    while True:
                        blocks_url = f"{self.api_base}/blocks/{page_id}/children?page_size=100"
                        if start_cursor:
                            blocks_url += f"&start_cursor={start_cursor}"
                        blocks_resp = await client.get(blocks_url, headers=self._headers())
                        if blocks_resp.status_code != 200:
                            break
                        b_json = blocks_resp.json()
                        blocks.extend(b_json.get("results", []))
                        if not b_json.get("has_more") or len(blocks) >= 500:
                            break
                        start_cursor = b_json.get("next_cursor")

                    full_text = f"# {title}\n\n" + self.render_blocks_to_text(blocks)
                    if full_text:
                        safe_title = title.replace("/", "_")
                        docs.append(
                            NormalizedDocument(
                                source_id=page_id,
                                document_id=page_id,
                                title=title,
                                content=full_text,
                                source_url=page_web_url,
                                filename=f"notion_{safe_title}.md",
                                mime_type="text/markdown",
                                version_tag=page_data.get("last_edited_time"),
                                metadata={
                                    "notion_page_id": page_id,
                                    "source_type": "notion",
                                    "url": page_web_url,
                                },
                            )
                        )
                except Exception as e:
                    logger.error(f"Failed to extract Notion page {page_id}: {e}")

        return docs
