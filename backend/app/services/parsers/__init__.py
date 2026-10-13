"""Parsers package for document ingestion."""

from app.services.parsers.base import DocumentParser, ParsedDocument, ParsedUnit
from app.services.parsers.csv_parser import CSVParser
from app.services.parsers.docx_parser import DOCXParser
from app.services.parsers.factory import ParserFactory
from app.services.parsers.html_parser import HTMLDocumentParser
from app.services.parsers.json_parser import JSONParser
from app.services.parsers.markdown_parser import MarkdownParser
from app.services.parsers.pdf_parser import PDFParser
from app.services.parsers.text_parser import TextParser
from app.services.parsers.xlsx_parser import XLSXParser

__all__ = [
    "DocumentParser",
    "ParsedDocument",
    "ParsedUnit",
    "ParserFactory",
    "PDFParser",
    "DOCXParser",
    "MarkdownParser",
    "CSVParser",
    "TextParser",
    "HTMLDocumentParser",
    "JSONParser",
    "XLSXParser",
]
