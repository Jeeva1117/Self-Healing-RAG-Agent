"""Website and documentation scraper connector with comprehensive SSRF protection, robots.txt compliance, and rate limiting."""

import asyncio
import ipaddress
import re
import socket
from typing import Any
from urllib.parse import urldefrag, urljoin, urlparse

import httpx

from app.core.logging import get_logger
from app.services.connectors.base import (
    BaseConnector,
    ConnectionTestResult,
    NormalizedDocument,
    SourceItem,
)
from app.services.parsers.html_parser import HTMLDocumentParser

logger = get_logger(__name__)

# Private and cloud metadata IP subnets prohibited for SSRF protection
BLOCKED_IP_NETWORKS = [
    ipaddress.ip_network("127.0.0.0/8"),  # Loopback
    ipaddress.ip_network("10.0.0.0/8"),  # Private RFC 1918
    ipaddress.ip_network("172.16.0.0/12"),  # Private RFC 1918
    ipaddress.ip_network("192.168.0.0/16"),  # Private RFC 1918
    ipaddress.ip_network("169.254.0.0/16"),  # Link-local & AWS/GCP/Azure Metadata
    ipaddress.ip_network("::1/128"),  # IPv6 loopback
    ipaddress.ip_network("fc00::/7"),  # IPv6 ULA
    ipaddress.ip_network("fe80::/10"),  # IPv6 Link-local
]

BLOCKED_HOSTNAMES = {
    "localhost",
    "metadata.google.internal",
    "instance-data",
}


def is_safe_url(url: str) -> tuple[bool, str]:
    """Validates that a URL is safe to fetch and does not target internal/private network assets."""
    try:
        parsed = urlparse(url)
        if parsed.scheme not in ("http", "https"):
            return False, f"Unsupported URL scheme '{parsed.scheme}'. Only http and https are allowed."

        hostname = parsed.hostname
        if not hostname:
            return False, "URL does not contain a valid hostname."

        if hostname.lower() in BLOCKED_HOSTNAMES:
            return False, f"Access to restricted hostname '{hostname}' is prohibited."

        # Resolve IP addresses
        addr_info = socket.getaddrinfo(hostname, None)
        if not addr_info:
            return False, f"Could not resolve domain '{hostname}'."

        for item in addr_info:
            ip_str = item[4][0]
            ip_obj = ipaddress.ip_address(ip_str)
            for blocked_net in BLOCKED_IP_NETWORKS:
                if ip_obj in blocked_net:
                    return False, f"Access to IP address '{ip_str}' is blocked (private/internal network protection)."

        return True, "URL is safe."
    except Exception as e:
        return False, f"URL validation failed: {str(e)}"


class SimpleRobotsTxt:
    """Parses standard robots.txt Disallow directives for polite web crawling."""

    def __init__(self, content: str):
        self.disallowed_prefixes: list[str] = []
        is_relevant_agent = True
        for raw_line in content.splitlines():
            line = raw_line.strip()
            if not line or line.startswith("#"):
                continue
            lower = line.lower()
            if lower.startswith("user-agent:"):
                agent = lower.split(":", 1)[1].strip()
                is_relevant_agent = agent in ("*", "self-healing-rag-agent", "bot")
            elif lower.startswith("disallow:") and is_relevant_agent:
                prefix = line.split(":", 1)[1].strip()
                if prefix:
                    self.disallowed_prefixes.append(prefix)

    def is_allowed(self, path: str) -> bool:
        norm_path = path or "/"
        for dis in self.disallowed_prefixes:
            if norm_path.startswith(dis):
                return False
        return True


async def fetch_with_safe_redirects(
    client: httpx.AsyncClient,
    url: str,
    max_redirects: int = 3,
    max_bytes: int = 5 * 1024 * 1024,
) -> httpx.Response:
    """Executes HTTP request enforcing strict SSRF validation across all redirect hops."""
    current_url = url
    for _ in range(max_redirects + 1):
        is_safe, reason = is_safe_url(current_url)
        if not is_safe:
            raise ValueError(f"SSRF violation on {current_url}: {reason}")

        resp = await client.get(current_url, follow_redirects=False)
        if 300 <= resp.status_code < 400 and "location" in resp.headers:
            current_url = urljoin(current_url, resp.headers["location"])
            continue

        content_len = resp.headers.get("content-length")
        if content_len and int(content_len) > max_bytes:
            raise ValueError(f"Page size exceeds maximum allowed limit ({max_bytes} bytes).")
        return resp
    raise ValueError(f"Exceeded maximum allowed redirects ({max_redirects}).")


class WebScraperConnector(BaseConnector):
    """Scrapes web pages and documentation sites, normalizing them into structured documents."""

    is_safe_url = staticmethod(is_safe_url)

    def __init__(self, config: dict[str, Any]):
        super().__init__(config)
        self.base_url = (config.get("root_url") or config.get("url") or config.get("base_url") or "").strip()
        self.max_pages = min(int(config.get("max_pages", 10)), 50)
        self.max_depth = min(int(config.get("max_depth", 2)), 3)
        self.timeout = float(config.get("timeout", 10.0))
        self.rate_limit_delay = float(config.get("rate_limit_delay", 0.05))
        self.parser = HTMLDocumentParser()

    async def test_connection(self) -> ConnectionTestResult:
        if not self.base_url:
            return ConnectionTestResult(
                success=False,
                message="Target URL is required.",
                can_browse=False,
            )

        is_safe, reason = is_safe_url(self.base_url)
        if not is_safe:
            return ConnectionTestResult(
                success=False,
                message=f"SSRF Security Violation: {reason}",
                can_browse=False,
            )

        try:
            headers = {"User-Agent": "Self-Healing-RAG-Agent/1.0 (+https://github.com/self-healing-rag)"}
            async with httpx.AsyncClient(timeout=self.timeout, headers=headers) as client:
                resp = await fetch_with_safe_redirects(client, self.base_url)

                if resp.status_code < 400:
                    return ConnectionTestResult(
                        success=True,
                        message=f"Successfully reached {self.base_url} (HTTP {resp.status_code})",
                        details={
                            "status_code": resp.status_code,
                            "content_type": resp.headers.get("content-type", "unknown"),
                        },
                        can_browse=True,
                    )
                else:
                    return ConnectionTestResult(
                        success=False,
                        message=f"Server returned HTTP error status {resp.status_code}",
                        can_browse=False,
                    )
        except Exception as e:
            return ConnectionTestResult(
                success=False,
                message=f"Failed to connect to website: {str(e)}",
                can_browse=False,
            )

    async def _fetch_robots_txt(self, client: httpx.AsyncClient) -> SimpleRobotsTxt | None:
        """Attempts to load robots.txt for domain to respect crawler policy."""
        try:
            parsed = urlparse(self.base_url)
            robots_url = f"{parsed.scheme}://{parsed.netloc}/robots.txt"
            is_safe, _ = is_safe_url(robots_url)
            if not is_safe:
                return None
            resp = await client.get(robots_url, timeout=5.0)
            if resp.status_code == 200:
                return SimpleRobotsTxt(resp.text)
        except Exception as e:
            logger.debug("Robots.txt check skipped or unavailable: %s", e)
        return None

    async def _discover_sitemap_urls(self, client: httpx.AsyncClient) -> list[str]:
        """Discovers indexable URLs via sitemap.xml if available."""
        try:
            parsed = urlparse(self.base_url)
            sitemap_url = f"{parsed.scheme}://{parsed.netloc}/sitemap.xml"
            is_safe, _ = is_safe_url(sitemap_url)
            if not is_safe:
                return []
            resp = await client.get(sitemap_url, timeout=5.0)
            if resp.status_code == 200:
                locs = re.findall(r"<loc>(https?://[^<]+)</loc>", resp.text)
                valid_locs = []
                for loc in locs:
                    clean_loc, _ = urldefrag(loc.strip())
                    if urlparse(clean_loc).netloc == parsed.netloc and is_safe_url(clean_loc)[0]:
                        valid_locs.append(clean_loc)
                return valid_locs[: self.max_pages]
        except Exception as e:
            logger.debug("Sitemap discovery skipped or unavailable: %s", e)
        return []

    async def list_sources(self, parent_id: str | None = None) -> list[SourceItem]:
        """Discovers linked pages starting from base_url up to max_pages, respecting robots.txt and sitemap."""
        if not self.base_url:
            return []

        is_safe, _ = is_safe_url(self.base_url)
        if not is_safe:
            return []

        discovered: list[SourceItem] = []
        visited = set()
        queue = [(self.base_url, 0)]
        base_domain = urlparse(self.base_url).netloc
        headers = {"User-Agent": "Self-Healing-RAG-Agent/1.0 (+https://github.com/self-healing-rag)"}

        async with httpx.AsyncClient(timeout=self.timeout, headers=headers) as client:
            robots = await self._fetch_robots_txt(client)

            # Check sitemap first
            sitemap_urls = await self._discover_sitemap_urls(client)
            for sm_url in sitemap_urls:
                if len(queue) < self.max_pages:
                    queue.append((sm_url, 1))

            while queue and len(discovered) < self.max_pages:
                current_url, depth = queue.pop(0)
                clean_url, _ = urldefrag(current_url)

                if clean_url in visited:
                    continue
                visited.add(clean_url)

                is_safe, _ = is_safe_url(clean_url)
                if not is_safe:
                    continue

                parsed_path = urlparse(clean_url).path
                if robots and not robots.is_allowed(parsed_path):
                    logger.debug("Skipping %s due to robots.txt Disallow", clean_url)
                    continue

                try:
                    await asyncio.sleep(self.rate_limit_delay)
                    resp = await fetch_with_safe_redirects(client, clean_url)
                    if resp.status_code != 200 or "text/html" not in resp.headers.get("content-type", ""):
                        continue

                    # Extract title
                    title_match = re.search(r"<title[^>]*>(.*?)</title>", resp.text, re.IGNORECASE | re.DOTALL)
                    page_title = title_match.group(1).strip() if title_match else clean_url

                    discovered.append(
                        SourceItem(
                            id=clean_url,
                            name=page_title,
                            item_type="url",
                            url=clean_url,
                            metadata={"depth": depth, "status_code": resp.status_code},
                        )
                    )

                    # Extract outgoing same-domain links if depth allows
                    if depth < self.max_depth:
                        links = re.findall(r'href=[\'"]([^\'" >]+)', resp.text)
                        for link in links:
                            abs_url = urljoin(clean_url, link)
                            abs_clean, _ = urldefrag(abs_url)
                            if urlparse(abs_clean).netloc == base_domain and abs_clean not in visited:
                                queue.append((abs_clean, depth + 1))
                except Exception as e:
                    logger.warning("Error discovering %s: %s", clean_url, e)

        return discovered

    async def extract_content(self, selected_ids: list[str]) -> list[NormalizedDocument]:
        """Fetches and normalizes the selected page URLs into structured documents."""
        docs: list[NormalizedDocument] = []
        headers = {"User-Agent": "Self-Healing-RAG-Agent/1.0 (+https://github.com/self-healing-rag)"}

        async with httpx.AsyncClient(timeout=self.timeout, headers=headers) as client:
            for url in selected_ids:
                is_safe, reason = is_safe_url(url)
                if not is_safe:
                    logger.warning("Skipping unsafe URL during extraction %s: %s", url, reason)
                    continue

                try:
                    await asyncio.sleep(self.rate_limit_delay)
                    resp = await fetch_with_safe_redirects(client, url)
                    if resp.status_code != 200:
                        continue

                    parsed_doc = self.parser.parse(resp.content, url)
                    page_title = parsed_doc.raw_metadata.get("title") or url
                    full_text = parsed_doc.full_text

                    if full_text.strip():
                        # Extract clean filename from URL path
                        path_part = urlparse(url).path.strip("/").replace("/", "_") or "index"
                        safe_filename = f"{path_part}.html"

                        docs.append(
                            NormalizedDocument(
                                source_id=url,
                                title=page_title,
                                content=full_text,
                                source_url=url,
                                filename=safe_filename,
                                mime_type="text/html",
                                metadata={
                                    "url": url,
                                    "source_type": "web",
                                    "title": page_title,
                                },
                            )
                        )
                except Exception as e:
                    logger.error("Failed to fetch content from %s: %s", url, e)

        return docs
