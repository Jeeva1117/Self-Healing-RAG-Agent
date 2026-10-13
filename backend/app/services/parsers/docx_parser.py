"""DOCX document parser extracting structural headings, paragraphs, and tables."""

import io
from typing import Any

from docx import Document

from app.core.logging import get_logger
from app.services.parsers.base import DocumentParser, ParsedDocument, ParsedUnit

logger = get_logger(__name__)


class DOCXParser(DocumentParser):
    """Parses Microsoft Word (.docx) documents preserving heading structure, paragraphs, and tables."""

    def parse(self, file_content: bytes, filename: str) -> ParsedDocument:
        try:
            doc = Document(io.BytesIO(file_content))
            units: list[ParsedUnit] = []
            current_section = "Introduction"
            current_paragraphs: list[str] = []
            unit_index = 1

            def flush_section():
                nonlocal unit_index, current_paragraphs
                if current_paragraphs:
                    section_text = "\n\n".join(current_paragraphs).strip()
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
                    current_paragraphs = []

            # Iterate over paragraphs
            for p in doc.paragraphs:
                text = p.text.strip()
                if not text:
                    continue

                style_name = p.style.name if p.style else ""
                is_heading = style_name.startswith("Heading") or style_name.startswith("Title")

                if is_heading:
                    flush_section()
                    current_section = text
                else:
                    current_paragraphs.append(text)

            # Flush remaining paragraphs
            flush_section()

            # Process tables
            for table_idx, table in enumerate(doc.tables, start=1):
                table_lines = []
                for row in table.rows:
                    cell_texts = [cell.text.strip().replace("\n", " ") for cell in row.cells]
                    # Filter out duplicate merged cell values in adjacent positions
                    deduped = []
                    for c in cell_texts:
                        if not deduped or c != deduped[-1]:
                            deduped.append(c)
                    table_lines.append(" | ".join(deduped))

                if table_lines:
                    table_text = "\n".join(table_lines)
                    units.append(
                        ParsedUnit(
                            text=table_text,
                            page_number=None,
                            section_title=f"Table {table_idx}",
                            unit_index=unit_index,
                            metadata={"table_index": table_idx},
                        )
                    )
                    unit_index += 1

            raw_metadata: dict[str, Any] = {
                "num_paragraphs": len(doc.paragraphs),
                "num_tables": len(doc.tables),
                "filename": filename,
            }

            if not units:
                return ParsedDocument(
                    units=[],
                    raw_metadata=raw_metadata,
                    error="EMPTY_DOCUMENT: DOCX file contains no readable text or tables.",
                )

            return ParsedDocument(units=units, raw_metadata=raw_metadata)

        except Exception as e:
            logger.error("Failed to parse DOCX %s: %s", filename, e, exc_info=True)
            return ParsedDocument(
                units=[],
                raw_metadata={"filename": filename},
                error=f"CORRUPT_OR_INVALID_DOCX: {str(e)}",
            )
