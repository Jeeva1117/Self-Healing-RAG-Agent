"""Google Drive connector using official Google Drive v3 REST API."""

from typing import Any

import httpx

from app.core.logging import get_logger
from app.services.connectors.base import (
    BaseConnector,
    ConnectionTestResult,
    NormalizedDocument,
    SourceItem,
)
from app.services.parsers.factory import ParserFactory

logger = get_logger(__name__)

# Supported Google Docs MIME types and export format mappings
GOOGLE_DOC_MIME_EXPORTS = {
    "application/vnd.google-apps.document": ("text/plain", "txt"),
    "application/vnd.google-apps.spreadsheet": ("text/csv", "csv"),
}

SUPPORTED_DRIVE_MIMES = {
    "application/vnd.google-apps.document",
    "application/vnd.google-apps.spreadsheet",
    "application/pdf",
    "text/plain",
    "text/markdown",
    "text/csv",
}


class GoogleDriveConnector(BaseConnector):
    """Integrates with Google Drive to list, select, and synchronize cloud documents."""

    def __init__(self, config: dict[str, Any]):
        super().__init__(config)
        self.access_token = (config.get("access_token") or config.get("token") or "").strip()
        self.folder_id = config.get("folder_id") or "root"
        self.api_base = "https://www.googleapis.com/drive/v3"

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self.access_token}",
            "Accept": "application/json",
        }

    async def test_connection(self) -> ConnectionTestResult:
        if not self.access_token:
            return ConnectionTestResult(
                success=False,
                message="Setup Required: Google Drive OAuth2 Access Token or Service Key is required (requires scope 'https://www.googleapis.com/auth/drive.readonly').",
                details={
                    "setup_instruction": (
                        "Configure a Google Cloud Project with the Google Drive API enabled. "
                        "Authorize with scope 'https://www.googleapis.com/auth/drive.readonly' "
                        "and provide the authorized access token."
                    )
                },
                can_browse=False,
            )

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                url = f"{self.api_base}/about?fields=user,storageQuota"
                resp = await client.get(url, headers=self._headers())

                if resp.status_code == 200:
                    data = resp.json()
                    user_info = data.get("user", {})
                    user_name = user_info.get("displayName", "Google User")
                    user_email = user_info.get("emailAddress", "unknown")
                    return ConnectionTestResult(
                        success=True,
                        message=f"Connected to Google Drive account ({user_name} <{user_email}>)",
                        details={"user": user_name, "email": user_email},
                        can_browse=True,
                    )
                elif resp.status_code == 401:
                    return ConnectionTestResult(
                        success=False,
                        message="Google Drive authorization expired or invalid. Please re-authenticate.",
                        can_browse=False,
                    )
                else:
                    return ConnectionTestResult(
                        success=False,
                        message=f"Google Drive API error (HTTP {resp.status_code}): {resp.text}",
                        can_browse=False,
                    )
        except Exception as e:
            return ConnectionTestResult(
                success=False,
                message=f"Failed to connect to Google Drive: {str(e)}",
                can_browse=False,
            )

    async def list_sources(self, parent_id: str | None = None) -> list[SourceItem]:
        """Lists accessible files and folders from Google Drive."""
        if not self.access_token:
            return []

        target_parent = parent_id or self.folder_id
        q = f"'{target_parent}' in parents and trashed = false"
        fields = "files(id, name, mimeType, size, modifiedTime, webViewLink)"

        items: list[SourceItem] = []
        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                url = f"{self.api_base}/files?q={q}&fields={fields}&pageSize=50"
                resp = await client.get(url, headers=self._headers())
                if resp.status_code != 200:
                    return []

                files = resp.json().get("files", [])
                for f in files:
                    mime = f.get("mimeType", "")
                    is_folder = mime == "application/vnd.google-apps.folder"
                    is_supported = is_folder or mime in SUPPORTED_DRIVE_MIMES

                    if is_supported:
                        items.append(
                            SourceItem(
                                id=f["id"],
                                name=f["name"],
                                item_type="folder" if is_folder else "file",
                                size_bytes=int(f["size"]) if "size" in f else None,
                                mime_type=mime,
                                url=f.get("webViewLink"),
                                selectable=not is_folder,
                                metadata={
                                    "modified_time": f.get("modifiedTime"),
                                    "is_google_doc": mime.startswith("application/vnd.google-apps."),
                                },
                            )
                        )
        except Exception as e:
            logger.error(f"Failed to list Google Drive files: {e}")

        return items

    async def extract_content(self, selected_ids: list[str]) -> list[NormalizedDocument]:
        """Downloads or exports the selected Google Drive files."""
        docs: list[NormalizedDocument] = []

        async with httpx.AsyncClient(timeout=20.0) as client:
            for file_id in selected_ids:
                try:
                    # Fetch file metadata
                    meta_url = f"{self.api_base}/files/{file_id}?fields=id,name,mimeType,webViewLink,modifiedTime"
                    meta_resp = await client.get(meta_url, headers=self._headers())
                    if meta_resp.status_code != 200:
                        continue

                    file_meta = meta_resp.json()
                    filename = file_meta.get("name", "document")
                    mime = file_meta.get("mimeType", "")
                    web_link = file_meta.get("webViewLink")

                    # Handle native Google Docs exports vs standard file downloads
                    if mime in GOOGLE_DOC_MIME_EXPORTS:
                        export_mime, ext = GOOGLE_DOC_MIME_EXPORTS[mime]
                        export_url = f"{self.api_base}/files/{file_id}/export?mimeType={export_mime}"
                        content_resp = await client.get(export_url, headers=self._headers())
                        text_content = content_resp.text
                        safe_filename = f"{filename}.{ext}" if not filename.endswith(f".{ext}") else filename
                    else:
                        download_url = f"{self.api_base}/files/{file_id}?alt=media"
                        content_resp = await client.get(download_url, headers=self._headers())
                        try:
                            parser = ParserFactory.get_parser(filename, mime)
                            parsed_doc = parser.parse(content_resp.content, filename)
                            text_content = parsed_doc.full_text
                        except Exception:
                            text_content = content_resp.text
                        safe_filename = filename

                    if text_content.strip():
                        docs.append(
                            NormalizedDocument(
                                source_id=file_id,
                                document_id=file_id,
                                title=filename,
                                content=text_content,
                                source_url=web_link,
                                filename=safe_filename,
                                version_tag=file_meta.get("modifiedTime"),
                                metadata={
                                    "drive_file_id": file_id,
                                    "modified_time": file_meta.get("modifiedTime"),
                                    "source_type": "gdrive",
                                    "mime_type": mime,
                                },
                            )
                        )
                except Exception as e:
                    logger.error(f"Failed to extract Drive file {file_id}: {e}")

        return docs
