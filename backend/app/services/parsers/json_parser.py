"""JSON document parser formatting structured JSON records into semantic text for vector search."""

import json

from app.core.logging import get_logger
from app.services.parsers.base import DocumentParser, ParsedDocument, ParsedUnit

logger = get_logger(__name__)


class JSONParser(DocumentParser):
    """Parses JSON files converting objects and collections into semantically readable records."""

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
                    error="EMPTY_DOCUMENT: JSON file is empty.",
                )

            data = json.loads(decoded)

            units: list[ParsedUnit] = []
            unit_index = 1

            if isinstance(data, list):
                # Array of records
                if not data:
                    return ParsedDocument(
                        units=[],
                        raw_metadata={"filename": filename, "item_count": 0},
                        error="EMPTY_DOCUMENT: JSON array contains no items.",
                    )

                # Batch records (e.g. 5 records per unit or 1 if large)
                batch_size = 5
                for i in range(0, len(data), batch_size):
                    batch = data[i : i + batch_size]
                    batch_texts = []
                    for idx, item in enumerate(batch, start=i + 1):
                        if isinstance(item, dict):
                            record_lines = [f"Record #{idx}:"]
                            for k, v in item.items():
                                val_str = json.dumps(v, ensure_ascii=False) if isinstance(v, (dict, list)) else str(v)
                                record_lines.append(f"  {k}: {val_str}")
                            batch_texts.append("\n".join(record_lines))
                        else:
                            batch_texts.append(f"Item #{idx}: {item}")

                    combined_text = "\n\n".join(batch_texts)
                    units.append(
                        ParsedUnit(
                            text=combined_text,
                            page_number=None,
                            section_title=f"Records {i + 1}-{min(i + batch_size, len(data))}",
                            unit_index=unit_index,
                            metadata={
                                "record_range": f"{i + 1}-{min(i + batch_size, len(data))}",
                                "total_records": len(data),
                                "filename": filename,
                            },
                        )
                    )
                    unit_index += 1

            elif isinstance(data, dict):
                if not data:
                    return ParsedDocument(
                        units=[],
                        raw_metadata={"filename": filename},
                        error="EMPTY_DOCUMENT: JSON object is empty.",
                    )

                # Separate nested arrays of dicts from scalar/nested object fields
                scalar_lines: list[str] = []
                for key, val in data.items():
                    if isinstance(val, list) and val and isinstance(val[0], dict):
                        # Format nested list of objects in batches
                        for i in range(0, len(val), 5):
                            batch = val[i : i + 5]
                            batch_lines = [f"Section: {key} (Items {i + 1} to {min(i + 5, len(val))})"]
                            for idx, sub_item in enumerate(batch, start=i + 1):
                                batch_lines.append(f"Item #{idx}:")
                                for sk, sv in sub_item.items():
                                    val_str = json.dumps(sv, ensure_ascii=False) if isinstance(sv, (dict, list)) else str(sv)
                                    batch_lines.append(f"  {sk}: {val_str}")
                            units.append(
                                ParsedUnit(
                                    text="\n".join(batch_lines),
                                    section_title=f"{key} [{i + 1}-{min(i + 5, len(val))}]",
                                    unit_index=unit_index,
                                    metadata={"section": key, "filename": filename},
                                )
                            )
                            unit_index += 1
                    else:
                        val_str = json.dumps(val, ensure_ascii=False) if isinstance(val, (dict, list)) else str(val)
                        scalar_lines.append(f"{key}: {val_str}")

                if scalar_lines:
                    # Group scalar properties into units of up to 10 lines
                    batch_size = 10
                    for i in range(0, len(scalar_lines), batch_size):
                        batch = scalar_lines[i : i + batch_size]
                        units.append(
                            ParsedUnit(
                                text="\n".join(batch),
                                section_title=f"Properties {i + 1}-{min(i + batch_size, len(scalar_lines))}",
                                unit_index=unit_index,
                                metadata={"filename": filename},
                            )
                        )
                        unit_index += 1
            else:
                # Primitive value
                units.append(
                    ParsedUnit(
                        text=str(data),
                        section_title="Data",
                        unit_index=1,
                        metadata={"filename": filename},
                    )
                )

            return ParsedDocument(
                units=units,
                raw_metadata={"filename": filename, "type": type(data).__name__},
            )
        except json.JSONDecodeError as jde:
            return ParsedDocument(
                units=[],
                raw_metadata={"filename": filename},
                error=f"INVALID_JSON: Failed to parse JSON document: {str(jde)}",
            )
        except Exception as e:
            logger.error(f"JSON parsing error for {filename}: {e}", exc_info=True)
            return ParsedDocument(
                units=[],
                raw_metadata={"filename": filename},
                error=f"PARSE_ERROR: Unexpected error parsing JSON: {str(e)}",
            )
