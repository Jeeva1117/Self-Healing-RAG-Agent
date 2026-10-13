"""Plain text document parser."""

from typing import Any

from app.core.logging import get_logger
from app.services.parsers.base import DocumentParser, ParsedDocument, ParsedUnit

logger = get_logger(__name__)


class TextParser(DocumentParser):
    """Parses plain text (.txt) files breaking into natural paragraphs/units."""

    def parse(self, file_content: bytes, filename: str) -> ParsedDocument:
        try:
            try:
                text = file_content.decode("utf-8")
            except UnicodeDecodeError:
                text = file_content.decode("latin-1", errors="replace")

            if not text.strip():
                return ParsedDocument(
                    units=[],
                    raw_metadata={"filename": filename},
                    error="EMPTY_DOCUMENT: Text file is empty.",
                )

            # Split by double newlines to form logical units
            paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
            units: list[ParsedUnit] = []

            for idx, p in enumerate(paragraphs, start=1):
                units.append(
                    ParsedUnit(
                        text=p,
                        page_number=None,
                        section_title=f"Section {idx}",
                        unit_index=idx,
                        metadata={"paragraph_index": idx},
                    )
                )

            raw_metadata: dict[str, Any] = {
                "num_paragraphs": len(units),
                "total_chars": len(text),
                "filename": filename,
            }

            return ParsedDocument(units=units, raw_metadata=raw_metadata)

        except Exception as e:
            logger.error("Failed to parse text file %s: %s", filename, e, exc_info=True)
            return ParsedDocument(
                units=[],
                raw_metadata={"filename": filename},
                error=f"CORRUPT_OR_INVALID_TXT: {str(e)}",
            )
