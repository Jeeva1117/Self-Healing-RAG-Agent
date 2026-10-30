"""PDF document parser preserving page boundaries and metadata."""

import io
from typing import Any

from pypdf import PdfReader

from app.core.logging import get_logger
from app.services.parsers.base import DocumentParser, ParsedDocument, ParsedUnit

logger = get_logger(__name__)


class PDFParser(DocumentParser):
    """Parses PDF documents page-by-page preserving page numbers and detecting scanned files."""

    def parse(self, file_content: bytes, filename: str) -> ParsedDocument:
        try:
            reader = PdfReader(io.BytesIO(file_content))
            if reader.is_encrypted:
                try:
                    decrypt_res = reader.decrypt("")
                    if decrypt_res == 0:
                        return ParsedDocument(
                            units=[],
                            raw_metadata={"filename": filename},
                            error="ENCRYPTED_PDF: Document is password protected and cannot be read without credentials.",
                        )
                except Exception:
                    return ParsedDocument(
                        units=[],
                        raw_metadata={"filename": filename},
                        error="ENCRYPTED_PDF: Document is password protected and cannot be read without credentials.",
                    )

            num_pages = len(reader.pages)
            if num_pages == 0:
                return ParsedDocument(
                    units=[],
                    raw_metadata={"num_pages": 0, "filename": filename},
                    error="EMPTY_DOCUMENT: PDF contains 0 pages.",
                )

            # Extract reader document metadata if available
            raw_metadata: dict[str, Any] = {
                "num_pages": num_pages,
                "filename": filename,
            }
            if reader.metadata:
                for k, v in reader.metadata.items():
                    if isinstance(v, str | int | float | bool):
                        # Strip leading slashes from PDF keys like /Title -> Title
                        clean_key = k.lstrip("/").lower()
                        raw_metadata[clean_key] = v

            units: list[ParsedUnit] = []
            total_chars = 0

            for page_idx, page in enumerate(reader.pages, start=1):
                try:
                    page_text = page.extract_text() or ""
                except Exception as extract_err:
                    logger.warning("Failed extracting page %d in %s: %s", page_idx, filename, extract_err)
                    page_text = ""

                clean_page_text = page_text.strip()
                total_chars += len(clean_page_text)

                if clean_page_text:
                    units.append(
                        ParsedUnit(
                            text=clean_page_text,
                            page_number=page_idx,
                            section_title=f"Page {page_idx}",
                            unit_index=page_idx,
                            metadata={"page": page_idx},
                        )
                    )

            # Scanned / Image-only PDF detection
            # If the PDF has pages but total extracted text across all pages is under 20 chars
            if total_chars < 20:
                logger.info("PDF %s detected as scanned/image-only (total text length: %d)", filename, total_chars)
                return ParsedDocument(
                    units=units,
                    raw_metadata=raw_metadata,
                    is_scanned=True,
                    error=(
                        "UNSUPPORTED_SCANNED_DOCUMENT: Document contains image-only or scanned pages "
                        "with no extractable text. OCR is required."
                    ),
                )


            return ParsedDocument(units=units, raw_metadata=raw_metadata)

        except Exception as e:
            logger.error("Failed to parse PDF %s: %s", filename, e, exc_info=True)
            return ParsedDocument(
                units=[],
                raw_metadata={"filename": filename},
                error=f"CORRUPT_OR_INVALID_PDF: {str(e)}",
            )
