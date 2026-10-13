"""Markdown document parser preserving headings, lists, code blocks, and section metadata."""

import re
from typing import Any

from app.core.logging import get_logger
from app.services.parsers.base import DocumentParser, ParsedDocument, ParsedUnit

logger = get_logger(__name__)

HEADING_REGEX = re.compile(r"^(#{1,6})\s+(.+)$")


class MarkdownParser(DocumentParser):
    """Parses Markdown documents preserving heading hierarchy, code blocks, and section metadata."""

    def parse(self, file_content: bytes, filename: str) -> ParsedDocument:
        try:
            # Decode content with UTF-8 or fallback
            try:
                text = file_content.decode("utf-8")
            except UnicodeDecodeError:
                text = file_content.decode("latin-1", errors="replace")

            if not text.strip():
                return ParsedDocument(
                    units=[],
                    raw_metadata={"filename": filename},
                    error="EMPTY_DOCUMENT: Markdown file is empty.",
                )

            lines = text.splitlines()
            units: list[ParsedUnit] = []
            current_section = "Overview"
            current_lines: list[str] = []
            unit_index = 1
            in_code_block = False

            def flush_section():
                nonlocal unit_index, current_lines
                if current_lines:
                    section_text = "\n".join(current_lines).strip()
                    if section_text:
                        units.append(
                            ParsedUnit(
                                text=section_text,
                                page_number=None,
                                section_title=current_section,
                                unit_index=unit_index,
                                metadata={"section": current_section},
                            )
                        )
                        unit_index += 1
                    current_lines = []

            for line in lines:
                stripped = line.strip()
                if stripped.startswith("```"):
                    in_code_block = not in_code_block
                    current_lines.append(line)
                    continue

                if not in_code_block:
                    match = HEADING_REGEX.match(stripped)
                    if match:
                        flush_section()
                        current_section = match.group(2).strip()
                        current_lines.append(line)
                        continue

                current_lines.append(line)

            flush_section()

            raw_metadata: dict[str, Any] = {
                "num_lines": len(lines),
                "num_sections": len(units),
                "filename": filename,
            }

            return ParsedDocument(units=units, raw_metadata=raw_metadata)

        except Exception as e:
            logger.error("Failed to parse Markdown %s: %s", filename, e, exc_info=True)
            return ParsedDocument(
                units=[],
                raw_metadata={"filename": filename},
                error=f"CORRUPT_OR_INVALID_MARKDOWN: {str(e)}",
            )
