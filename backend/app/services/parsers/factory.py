"""Factory for selecting document parsers based on filename extension or MIME type."""

from app.core.exceptions import AppError
from app.services.parsers.base import DocumentParser
from app.services.parsers.csv_parser import CSVParser
from app.services.parsers.docx_parser import DOCXParser
from app.services.parsers.html_parser import HTMLDocumentParser
from app.services.parsers.json_parser import JSONParser
from app.services.parsers.markdown_parser import MarkdownParser
from app.services.parsers.pdf_parser import PDFParser
from app.services.parsers.text_parser import TextParser
from app.services.parsers.xlsx_parser import XLSXParser


class ParserFactory:
    """Provides document parsers based on file extension and MIME type."""

    _PARSER_MAP = {
        "pdf": PDFParser,
        "docx": DOCXParser,
        "txt": TextParser,
        "text": TextParser,
        "md": MarkdownParser,
        "markdown": MarkdownParser,
        "csv": CSVParser,
        "html": HTMLDocumentParser,
        "htm": HTMLDocumentParser,
        "json": JSONParser,
        "xlsx": XLSXParser,
    }

    _MIME_MAP = {
        "application/pdf": PDFParser,
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document": DOCXParser,
        "application/msword": DOCXParser,
        "text/plain": TextParser,
        "text/markdown": MarkdownParser,
        "text/x-markdown": MarkdownParser,
        "text/csv": CSVParser,
        "application/csv": CSVParser,
        "text/html": HTMLDocumentParser,
        "application/xhtml+xml": HTMLDocumentParser,
        "application/json": JSONParser,
        "text/json": JSONParser,
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": XLSXParser,
    }

    @classmethod
    def get_parser(cls, filename: str, content_type: str | None = None) -> DocumentParser:
        """Finds the parser for a given filename or MIME content type.

        Raises:
            AppError if the document format is unsupported.
        """
        # 1. Try extension first
        ext = filename.split(".")[-1].lower() if "." in filename else ""
        if ext in cls._PARSER_MAP:
            return cls._PARSER_MAP[ext]()

        # 2. Try MIME type
        if content_type:
            clean_mime = content_type.split(";")[0].strip().lower()
            if clean_mime in cls._MIME_MAP:
                return cls._MIME_MAP[clean_mime]()

        supported = list(cls._PARSER_MAP.keys())
        formats_str = ", ".join(sorted(set(supported)))
        raise AppError(
            code="UNSUPPORTED_DOCUMENT_FORMAT",
            message=f"Unsupported document format '{ext or content_type}'. Supported formats: {formats_str}",
            status_code=400,
        )
