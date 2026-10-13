"""GitHub repository connector using official GitHub REST API with secret exclusion."""

import base64
import re
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

# Patterns of files strictly excluded for security and cleanliness
EXCLUDED_PATTERNS = {
    ".env", ".env.local", ".env.production",
    "id_rsa", "id_ed25519", "id_dsa",
    ".git", ".github",
    "node_modules", "vendor", "__pycache__", ".venv", "venv",
}

EXCLUDED_EXTENSIONS = {
    ".pem", ".key", ".pfx", ".p12", ".exe", ".dll", ".so", ".dylib",
    ".zip", ".tar", ".gz", ".7z", ".png", ".jpg", ".jpeg", ".gif",
    ".svg", ".ico", ".woff", ".woff2", ".ttf", ".eot", ".mp4", ".mp3",
    ".pyc", ".pyo", ".class", ".jar",
}

SUPPORTED_CODE_DOC_EXTENSIONS = {
    ".md", ".markdown", ".txt", ".rst", ".adoc",
    ".py", ".ts", ".tsx", ".js", ".jsx", ".html",
    ".json", ".yaml", ".yml", ".toml", ".sql", ".sh",
    ".java", ".go", ".rs", ".c", ".cpp", ".h", ".cs", ".rb", ".php",
}

SECRET_PATTERNS = [
    re.compile(r"ghp_[a-zA-Z0-9]{36}"),
    re.compile(r"github_pat_[a-zA-Z0-9_]{82}"),
    re.compile(r"AKIA[0-9A-Z]{16}"),
    re.compile(r"-----BEGIN (?:RSA|EC|OPENSSH|DSA|PGP)? PRIVATE KEY-----[\s\S]*?-----END (?:RSA|EC|OPENSSH|DSA|PGP)? PRIVATE KEY-----"),
    re.compile(r"(?:api_key|secret_key|jwt_secret)\s*[:=]\s*['\"][^\s'\"]{8,}['\"]", re.IGNORECASE),
]


def sanitize_secrets(text: str) -> str:
    """Detects and redacts detected secrets and API credentials from repository files."""
    sanitized = text
    for pattern in SECRET_PATTERNS:
        sanitized = pattern.sub("[REDACTED_SECRET]", sanitized)
    return sanitized


class GitHubConnector(BaseConnector):
    """Integrates with GitHub to discover, filter, and extract repository documentation."""

    sanitize_secrets = staticmethod(sanitize_secrets)

    def __init__(self, config: dict[str, Any]):
        super().__init__(config)
        self.token = (
            config.get("personal_access_token")
            or config.get("access_token")
            or config.get("token")
            or ""
        ).strip()
        self.repo = (config.get("repository") or config.get("repo") or "").strip()  # "owner/repo"
        self.branch = (config.get("branch") or "main").strip()
        self.api_base = "https://api.github.com"

    @staticmethod
    def _is_prohibited_path(path: str) -> bool:
        """Determines if a repository path represents sensitive credentials, binary, or excluded files."""
        norm = path.replace("\\", "/").strip("/")
        parts = norm.split("/")
        filename = parts[-1].lower() if parts else ""

        for part in parts:
            part_lower = part.lower()
            if part_lower in {"node_modules", "vendor", "__pycache__", ".venv", "venv", ".git", ".github"}:
                return True
            if part_lower == ".env" or part_lower.startswith(".env.") or ".env." in part_lower:
                return True
            if part_lower in {"id_rsa", "id_ed25519", "id_dsa", ".ds_store"}:
                return True

        # Check file extension
        ext = "." + filename.split(".")[-1].lower() if "." in filename else ""
        if ext in EXCLUDED_EXTENSIONS:
            return True

        return False

    def _headers(self) -> dict[str, str]:
        headers = {
            "Accept": "application/vnd.github+json",
            "User-Agent": "Self-Healing-RAG-Agent",
        }
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        return headers

    async def test_connection(self) -> ConnectionTestResult:
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                if self.repo:
                    # Test specific repository access
                    url = f"{self.api_base}/repos/{self.repo}"
                    resp = await client.get(url, headers=self._headers())
                    if resp.status_code == 200:
                        repo_data = resp.json()
                        default_branch = repo_data.get("default_branch", "main")
                        return ConnectionTestResult(
                            success=True,
                            message=f"Connected to {self.repo} (Default Branch: {default_branch})",
                            details={
                                "full_name": repo_data.get("full_name"),
                                "private": repo_data.get("private"),
                                "default_branch": default_branch,
                            },
                            can_browse=True,
                        )
                    elif resp.status_code == 404:
                        return ConnectionTestResult(
                            success=False,
                            message=f"Repository '{self.repo}' not found or token lacks permission.",
                            can_browse=False,
                        )
                    elif resp.status_code == 401:
                        return ConnectionTestResult(
                            success=False,
                            message="Invalid or expired GitHub Personal Access Token.",
                            can_browse=False,
                        )
                    else:
                        return ConnectionTestResult(
                            success=False,
                            message=f"GitHub API returned HTTP {resp.status_code}: {resp.text}",
                            can_browse=False,
                        )
                else:
                    # Test user account access
                    if not self.token:
                        return ConnectionTestResult(
                            success=False,
                            message="Either a repository name or GitHub Personal Access Token is required.",
                            can_browse=False,
                        )
                    url = f"{self.api_base}/user"
                    resp = await client.get(url, headers=self._headers())
                    if resp.status_code == 200:
                        user_data = resp.json()
                        return ConnectionTestResult(
                            success=True,
                            message=f"Authenticated as GitHub user @{user_data.get('login')}",
                            details={"login": user_data.get("login")},
                            can_browse=True,
                        )
                    else:
                        return ConnectionTestResult(
                            success=False,
                            message="Invalid GitHub Personal Access Token.",
                            can_browse=False,
                        )
        except Exception as e:
            return ConnectionTestResult(
                success=False,
                message=f"Failed to connect to GitHub: {str(e)}",
                can_browse=False,
            )

    async def list_sources(self, parent_id: str | None = None) -> list[SourceItem]:
        """Lists files and folders from the repository git tree."""
        if not self.repo:
            # If no repo specified but user is authenticated, list user repositories
            if not self.token:
                return []
            try:
                async with httpx.AsyncClient(timeout=10.0) as client:
                    resp = await client.get(f"{self.api_base}/user/repos?per_page=30", headers=self._headers())
                    if resp.status_code == 200:
                        repos = resp.json()
                        return [
                            SourceItem(
                                id=r["full_name"],
                                name=r["name"],
                                item_type="repository",
                                url=r["html_url"],
                                metadata={"private": r["private"], "description": r.get("description")},
                            )
                            for r in repos
                        ]
            except Exception as e:
                logger.error(f"Failed to list GitHub repos: {e}")
                return []

        # List tree in repository
        items: list[SourceItem] = []
        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                url = f"{self.api_base}/repos/{self.repo}/git/trees/{self.branch}?recursive=1"
                resp = await client.get(url, headers=self._headers())
                if resp.status_code != 200:
                    return []

                tree_data = resp.json().get("tree", [])
                for entry in tree_data:
                    path = entry.get("path", "")
                    entry_type = entry.get("type", "")

                    if entry_type != "blob":
                        continue

                    # Filter excluded paths and files
                    if self._is_prohibited_path(path):
                        continue

                    ext = "." + path.split(".")[-1].lower() if "." in path else ""

                    # Only show text, docs, and code files
                    if ext in SUPPORTED_CODE_DOC_EXTENSIONS or path.lower() in ("readme", "license", "contributing"):
                        file_name = path.split("/")[-1] if "/" in path else path
                        items.append(
                            SourceItem(
                                id=path,
                                name=file_name,
                                item_type="file",
                                path=path,
                                size_bytes=entry.get("size", 0),
                                url=f"https://github.com/{self.repo}/blob/{self.branch}/{path}",
                                metadata={
                                    "sha": entry.get("sha"),
                                    "repo": self.repo,
                                    "branch": self.branch,
                                },
                            )
                        )
        except Exception as e:
            logger.error(f"Failed to list GitHub files for {self.repo}: {e}")

        return items[:100]  # Cap at 100 files per view

    async def extract_content(self, selected_ids: list[str]) -> list[NormalizedDocument]:
        """Fetches contents of selected file paths from repository."""
        docs: list[NormalizedDocument] = []

        async with httpx.AsyncClient(timeout=15.0) as client:
            for path in selected_ids:
                try:
                    url = f"{self.api_base}/repos/{self.repo}/contents/{path}?ref={self.branch}"
                    resp = await client.get(url, headers=self._headers())
                    if resp.status_code != 200:
                        continue

                    data = resp.json()
                    encoding = data.get("encoding")
                    content_raw = data.get("content", "")

                    if encoding == "base64":
                        text_content = base64.b64decode(content_raw).decode("utf-8", errors="replace")
                    else:
                        text_content = content_raw

                    clean_text = sanitize_secrets(text_content)
                    if clean_text.strip():
                        file_title = f"{self.repo} / {path}"
                        source_url = f"https://github.com/{self.repo}/blob/{self.branch}/{path}"
                        safe_filename = path.replace("/", "_")

                        docs.append(
                            NormalizedDocument(
                                source_id=path,
                                source_path=path,
                                title=file_title,
                                content=clean_text,
                                source_url=source_url,
                                filename=safe_filename,
                                version_tag=data.get("sha"),
                                author=self.repo.split("/")[0] if "/" in self.repo else None,
                                metadata={
                                    "repository": self.repo,
                                    "branch": self.branch,
                                    "path": path,
                                    "sha": data.get("sha"),
                                    "source_type": "github",
                                },
                            )
                        )
                except Exception as e:
                    logger.error(f"Failed to extract file {path} from GitHub: {e}")

        return docs
