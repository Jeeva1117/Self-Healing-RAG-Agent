"""CSV document parser converting tabular rows into semantic text representations."""

import csv
import io
from typing import Any

from app.core.logging import get_logger
from app.services.parsers.base import DocumentParser, ParsedDocument, ParsedUnit

logger = get_logger(__name__)


class CSVParser(DocumentParser):
    """Parses CSV files converting structured rows into key-value pairs suitable for vector retrieval."""

    def parse(self, file_content: bytes, filename: str) -> ParsedDocument:
        try:
            try:
                decoded_str = file_content.decode("utf-8")
            except UnicodeDecodeError:
                decoded_str = file_content.decode("latin-1", errors="replace")

            if not decoded_str.strip():
                return ParsedDocument(
                    units=[],
                    raw_metadata={"filename": filename},
                    error="EMPTY_DOCUMENT: CSV file is empty.",
                )

            # Detect delimiter using Sniffer if possible, fallback to comma
            stream = io.StringIO(decoded_str)
            try:
                sample = stream.read(2048)
                stream.seek(0)
                dialect = csv.Sniffer().sniff(sample)
                reader = csv.reader(stream, dialect)
            except Exception:
                stream.seek(0)
                reader = csv.reader(stream)

            rows = list(reader)
            if not rows:
                return ParsedDocument(
                    units=[],
                    raw_metadata={"filename": filename},
                    error="EMPTY_DOCUMENT: No rows found in CSV.",
                )

            headers = [h.strip() for h in rows[0]]
            data_rows = rows[1:]

            if not data_rows:
                return ParsedDocument(
                    units=[],
                    raw_metadata={"headers": headers, "filename": filename},
                    error="EMPTY_DOCUMENT: CSV contains headers but no data rows.",
                )

            units: list[ParsedUnit] = []
            # Group rows into manageable batches (e.g., 5 rows per unit) to preserve context
            BATCH_SIZE = 5
            for batch_start in range(0, len(data_rows), BATCH_SIZE):
                batch_rows = data_rows[batch_start : batch_start + BATCH_SIZE]
                formatted_records = []

                for idx, row in enumerate(batch_rows, start=batch_start + 1):
                    # Format as Key: Value pairs
                    record_parts = []
                    for h_idx, header in enumerate(headers):
                        val = row[h_idx].strip() if h_idx < len(row) else ""
                        if val:
                            record_parts.append(f"{header}: {val}")
                        else:
                            record_parts.append(f"{header}: N/A")
                    formatted_records.append(f"Row {idx} -> " + " | ".join(record_parts))

                unit_text = "\n".join(formatted_records)
                units.append(
                    ParsedUnit(
                        text=unit_text,
                        page_number=None,
                        section_title=f"Rows {batch_start + 1} to {min(batch_start + BATCH_SIZE, len(data_rows))}",
                        unit_index=(batch_start // BATCH_SIZE) + 1,
                        metadata={
                            "start_row": batch_start + 1,
                            "end_row": min(batch_start + BATCH_SIZE, len(data_rows)),
                            "total_columns": len(headers),
                        },
                    )
                )

            raw_metadata: dict[str, Any] = {
                "headers": headers,
                "total_rows": len(data_rows),
                "total_columns": len(headers),
                "filename": filename,
            }

            return ParsedDocument(units=units, raw_metadata=raw_metadata)

        except Exception as e:
            logger.error("Failed to parse CSV %s: %s", filename, e, exc_info=True)
            return ParsedDocument(
                units=[],
                raw_metadata={"filename": filename},
                error=f"CORRUPT_OR_INVALID_CSV: {str(e)}",
            )
