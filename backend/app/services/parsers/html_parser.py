"""HTML document parser preserving titles, structural headings, tables, and content sections."""

import re
from html.parser import HTMLParser
from typing import Any

from app.core.logging import get_logger
from app.services.parsers.base import DocumentParser, ParsedDocument, ParsedUnit

logger = get_logger(__name__)


class _HTMLTextExtractor(HTMLParser):
    """Internal streaming HTML parser extracting readable text and structural sections."""

    def __init__(self):
        super().__init__()
        self.title: str = ""
        self.sections: list[dict[str, Any]] = []
        self._current_tag: str = ""
        self._current_text: list[str] = []
        self._current_heading: str = "Introduction"
        self._in_title = False
        self._in_skip_tag = False
        self._skip_tags = {"script", "style", "noscript", "svg"}

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]):
        tag_lower = tag.lower()
        if tag_lower in self._skip_tags:
            self._in_skip_tag = True
            return

        if tag_lower == "title":
            self._in_title = True
            return

        if tag_lower in {"h1", "h2", "h3", "h4", "h5", "h6"}:
            self._flush_section()
            self._current_tag = tag_lower
        elif tag_lower in {"p", "div", "section", "article", "tr", "li"}:
            self._current_text.append("\n")

    def handle_endtag(self, tag: str):
        tag_lower = tag.lower()
        if tag_lower in self._skip_tags:
            self._in_skip_tag = False
            return

        if tag_lower == "title":
            self._in_title = False
            return

        if tag_lower in {"h1", "h2", "h3", "h4", "h5", "h6"}:
            heading_text = "".join(self._current_text).strip()
            self._current_text = []
            if heading_text:
                self._current_heading = heading_text
        elif tag_lower in {"p", "tr", "li"}:
            self._current_text.append("\n")

    def handle_data(self, data: str):
        if self._in_skip_tag:
            return

        text = data.strip()
        if not text:
            return

        if self._in_title:
            self.title += " " + text
        else:
            self._current_text.append(" " + text)

    def _flush_section(self):
        content = "".join(self._current_text).strip()
        self._current_text = []
        # Collapse multiple newlines/spaces
        cleaned_content = re.sub(r"\n{3,}", "\n\n", content).strip()
        if cleaned_content:
            section_text = (
                f"{self._current_heading}\n\n{cleaned_content}"
                if self._current_heading and self._current_heading != "Introduction"
                else cleaned_content
            )
            self.sections.append(
                {
                    "heading": self._current_heading,
                    "text": section_text,
                }
            )

    def close(self):
        super().close()
        self._flush_section()


class HTMLDocumentParser(DocumentParser):
    """Parses HTML documents into clean semantic units preserving headings and hierarchy."""

    def parse(self, file_content: bytes, filename: str) -> ParsedDocument:
        try:
            try:
                decoded = file_content.decode("utf-8")
            except UnicodeDecodeError:
                decoded = file_content.decode("latin-1", errors="replace")

            if not decoded.strip():
                return ParsedDocument(
                    units=[],
                    raw_metadata={"filename": filename},
                    error="EMPTY_DOCUMENT: HTML content is empty.",
                )

            extractor = _HTMLTextExtractor()
            extractor.feed(decoded)
            extractor.close()

            doc_title = extractor.title.strip() or filename
            units: list[ParsedUnit] = []

            for idx, sec in enumerate(extractor.sections, start=1):
                units.append(
                    ParsedUnit(
                        text=sec["text"],
                        page_number=None,
                        section_title=sec["heading"],
                        unit_index=idx,
                        metadata={
                            "section": sec["heading"],
                            "title": doc_title,
                            "filename": filename,
                        },
                    )
                )

            if units and doc_title and doc_title != filename:
                if doc_title not in units[0].text:
                    units[0].text = f"{doc_title}\n\n{units[0].text}"

            if not units:
                # Fallback: extract plain text if no clear sections were parsed
                raw_text = re.sub(r"<[^>]+>", " ", decoded)
                raw_text = re.sub(r"\s+", " ", raw_text).strip()
                if raw_text:
                    units.append(
                        ParsedUnit(
                            text=raw_text,
                            section_title=doc_title,
                            unit_index=1,
                            metadata={"title": doc_title, "filename": filename},
                        )
                    )

            if not units:
                return ParsedDocument(
                    units=[],
                    raw_metadata={"filename": filename, "title": doc_title},
                    error="EMPTY_DOCUMENT: No readable text extracted from HTML.",
                )

            return ParsedDocument(
                units=units,
                raw_metadata={"filename": filename, "title": doc_title},
            )
        except Exception as e:
            logger.error(f"HTML parsing failed for {filename}: {e}", exc_info=True)
            return ParsedDocument(
                units=[],
                raw_metadata={"filename": filename},
                error=f"PARSE_ERROR: Failed to parse HTML document: {str(e)}",
            )
