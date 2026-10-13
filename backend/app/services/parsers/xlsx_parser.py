"""XLSX spreadsheet parser extracting sheets, rows, and columns into semantic tabular text."""

import io
import xml.etree.ElementTree as ET
import zipfile

from app.core.logging import get_logger
from app.services.parsers.base import DocumentParser, ParsedDocument, ParsedUnit

logger = get_logger(__name__)

# XML namespaces commonly used in OpenXML spreadsheets
NS = {
    "main": "http://schemas.openxmlformats.org/spreadsheetml/2006/main",
    "r": "http://schemas.openxmlformats.org/officeDocument/2006/relationships",
}


class XLSXParser(DocumentParser):
    """Parses Excel (.xlsx) spreadsheets extracting sheets, rows, and cell values into structured units."""

    def parse(self, file_content: bytes, filename: str) -> ParsedDocument:
        try:
            if not file_content:
                return ParsedDocument(
                    units=[],
                    raw_metadata={"filename": filename},
                    error="EMPTY_DOCUMENT: Excel file is empty.",
                )

            try:
                zf = zipfile.ZipFile(io.BytesIO(file_content))
            except zipfile.BadZipFile:
                return ParsedDocument(
                    units=[],
                    raw_metadata={"filename": filename},
                    error="CORRUPT_XLSX_ARCHIVE: File is not a valid zip archive / Excel document.",
                )

            # 1. Read shared strings if present
            shared_strings: list[str] = []
            if "xl/sharedStrings.xml" in zf.namelist():
                ss_data = zf.read("xl/sharedStrings.xml")
                ss_root = ET.fromstring(ss_data)
                for si in ss_root.findall(".//main:si", NS) or ss_root.findall(".//{http://schemas.openxmlformats.org/spreadsheetml/2006/main}si"):
                    text_parts = []
                    for t in si.iter():
                        if t.tag.endswith("t") and t.text:
                            text_parts.append(t.text)
                    shared_strings.append("".join(text_parts))

            # 2. Discover sheets from workbook.xml
            sheet_names: list[str] = []
            if "xl/workbook.xml" in zf.namelist():
                wb_data = zf.read("xl/workbook.xml")
                wb_root = ET.fromstring(wb_data)
                for sheet in wb_root.findall(".//main:sheet", NS) or wb_root.findall(".//{http://schemas.openxmlformats.org/spreadsheetml/2006/main}sheet"):
                    sheet_names.append(sheet.attrib.get("name", "Sheet"))

            # 3. Read worksheets
            worksheet_files = sorted([f for f in zf.namelist() if f.startswith("xl/worksheets/sheet") and f.endswith(".xml")])
            if not worksheet_files:
                return ParsedDocument(
                    units=[],
                    raw_metadata={"filename": filename},
                    error="EMPTY_DOCUMENT: No worksheets found in Excel workbook.",
                )

            units: list[ParsedUnit] = []
            unit_index = 1

            for s_idx, ws_file in enumerate(worksheet_files):
                sheet_title = sheet_names[s_idx] if s_idx < len(sheet_names) else f"Sheet {s_idx + 1}"
                ws_data = zf.read(ws_file)
                ws_root = ET.fromstring(ws_data)

                rows_data: list[list[str]] = []
                # Find all row elements
                rows = ws_root.findall(".//main:row", NS) or ws_root.findall(".//{http://schemas.openxmlformats.org/spreadsheetml/2006/main}row")
                for row in rows:
                    row_cells: list[str] = []
                    cells = row.findall(".//main:c", NS) or row.findall(".//{http://schemas.openxmlformats.org/spreadsheetml/2006/main}c")
                    for c in cells:
                        cell_type = c.attrib.get("t")
                        v_elem = c.find(".//main:v", NS) if c.find(".//main:v", NS) is not None else c.find(".//{http://schemas.openxmlformats.org/spreadsheetml/2006/main}v")
                        val = ""
                        if v_elem is not None and v_elem.text:
                            val = v_elem.text
                            if cell_type == "s":
                                # shared string index
                                try:
                                    s_idx_val = int(val)
                                    if 0 <= s_idx_val < len(shared_strings):
                                        val = shared_strings[s_idx_val]
                                except (ValueError, IndexError):
                                    pass
                        row_cells.append(val.strip())
                    if any(c for c in row_cells):
                        rows_data.append(row_cells)

                if not rows_data:
                    continue

                headers = rows_data[0]
                data_rows = rows_data[1:] if len(rows_data) > 1 else []

                if not data_rows:
                    # Single row of headers or single record
                    text_lines = [f"Sheet [{sheet_title}] Row 1: " + " | ".join(headers)]
                    units.append(
                        ParsedUnit(
                            text="\n".join(text_lines),
                            section_title=sheet_title,
                            unit_index=unit_index,
                            metadata={"sheet": sheet_title, "filename": filename},
                        )
                    )
                    unit_index += 1
                else:
                    # Batch rows into groups of 5 with header context
                    batch_size = 5
                    for b_start in range(0, len(data_rows), batch_size):
                        batch = data_rows[b_start : b_start + batch_size]
                        batch_lines = [f"Sheet: {sheet_title}"]
                        for r_offset, r in enumerate(batch):
                            row_num = b_start + r_offset + 2
                            row_parts = []
                            for c_idx, val in enumerate(r):
                                col_name = headers[c_idx] if c_idx < len(headers) and headers[c_idx] else f"Col_{c_idx + 1}"
                                if val:
                                    row_parts.append(f"{col_name}: {val}")
                            if row_parts:
                                batch_lines.append(f"Row {row_num}: " + ", ".join(row_parts))

                        if len(batch_lines) > 1:
                            units.append(
                                ParsedUnit(
                                    text="\n".join(batch_lines),
                                    section_title=f"{sheet_title} (Rows {b_start + 2}-{min(b_start + batch_size + 1, len(data_rows) + 1)})",
                                    unit_index=unit_index,
                                    metadata={
                                        "sheet": sheet_title,
                                        "row_range": f"{b_start + 2}-{min(b_start + batch_size + 1, len(data_rows) + 1)}",
                                        "filename": filename,
                                    },
                                )
                            )
                            unit_index += 1

            if not units:
                return ParsedDocument(
                    units=[],
                    raw_metadata={"filename": filename},
                    error="EMPTY_DOCUMENT: No readable text or non-empty cells found in spreadsheet.",
                )

            return ParsedDocument(
                units=units,
                raw_metadata={"filename": filename, "sheets": sheet_names},
            )
        except Exception as e:
            logger.error(f"Failed parsing XLSX document {filename}: {e}", exc_info=True)
            return ParsedDocument(
                units=[],
                raw_metadata={"filename": filename},
                error=f"PARSE_ERROR: Failed to parse XLSX document: {str(e)}",
            )
