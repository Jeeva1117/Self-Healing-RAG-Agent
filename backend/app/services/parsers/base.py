"""Base abstractions and data structures for document parsing."""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any


@dataclass
class ParsedUnit:
    """A single structural unit extracted from a document (e.g. a page, section, or row)."""

    text: str
    page_number: int | None = None
    section_title: str | None = None
    unit_index: int = 0
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class ParsedDocument:
    """Complete structured output from a document parser."""

    units: list[ParsedUnit]
    raw_metadata: dict[str, Any] = field(default_factory=dict)
    is_scanned: bool = False
    error: str | None = None

    @property
    def total_text_length(self) -> int:
        return sum(len(u.text) for u in self.units)

    @property
    def full_text(self) -> str:
        return "\n\n".join(u.text for u in self.units if u.text.strip())


class DocumentParser(ABC):
    """Abstract interface for file-format specific parsers."""

    @abstractmethod
    def parse(self, file_content: bytes, filename: str) -> ParsedDocument:
        """Parses raw document bytes into structured units.

        Args:
            file_content: Raw byte content of the file.
            filename: Original filename for context.

        Returns:
            ParsedDocument containing structured units and metadata.
        """
        pass
