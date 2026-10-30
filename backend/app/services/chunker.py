"""Structure-aware document chunking service preserving citation metadata."""

import re
from dataclasses import dataclass, field
from typing import Any

from app.core.config import settings
from app.services.parsers.base import ParsedDocument, ParsedUnit


@dataclass
class ChunkResult:
    """A single generated chunk with full citation metadata."""

    content: str
    chunk_index: int
    page_number: int | None
    section_title: str | None
    token_count: int
    character_count: int
    start_offset: int
    end_offset: int
    metadata: dict[str, Any] = field(default_factory=dict)


class DocumentChunker:
    """Intelligently chunks parsed document units respecting sections, paragraphs, and boundaries."""

    def __init__(
        self,
        chunk_size: int | None = None,
        chunk_overlap: int | None = None,
        min_chunk_length: int = 20,
    ):
        # chunk_size in characters (typically ~3.5-4 chars per token, so 500 tokens ~ 2000 chars)
        # Using settings.CHUNK_SIZE * 4 as target character limit if CHUNK_SIZE represents tokens
        target_tokens = chunk_size or settings.CHUNK_SIZE
        target_overlap_tokens = chunk_overlap or settings.CHUNK_OVERLAP

        self.target_tokens = target_tokens
        self.target_overlap_tokens = target_overlap_tokens
        self.chunk_char_size = max(100, target_tokens * 4)
        self.overlap_char_size = max(10, target_overlap_tokens * 4)
        self.min_chunk_length = min_chunk_length

    @staticmethod
    def estimate_tokens(text: str) -> int:
        """Approximates token count using standard ~4 characters per token heuristic."""
        if not text:
            return 0
        words = len(text.split())
        char_est = len(text) // 4
        # Blend word count and character count for robust estimation
        return max(1, int(0.7 * char_est + 0.3 * words))

    def chunk_document(
        self,
        parsed_doc: ParsedDocument,
        document_id: str,
        document_version_id: str | None = None,
        source_filename: str = "",
    ) -> list[ChunkResult]:
        """Splits all units of a ParsedDocument into structured, overlapping chunks."""
        chunks: list[ChunkResult] = []
        global_offset = 0
        chunk_idx = 0

        for unit in parsed_doc.units:
            text = unit.text.strip()
            if not text:
                continue

            unit_chunks = self._chunk_unit(
                unit=unit,
                start_global_offset=global_offset,
                start_chunk_idx=chunk_idx,
                document_id=document_id,
                document_version_id=document_version_id,
                source_filename=source_filename,
            )

            chunks.extend(unit_chunks)
            chunk_idx += len(unit_chunks)
            global_offset += len(text) + 2  # account for unit separator

        return chunks

    @staticmethod
    def _is_numbered_heading(line: str) -> bool:
        """Detects numbered structural headings like '1. Variables', '4. Operators', '20. OOP'."""
        s = line.strip()
        return bool(re.match(r"^\d+[\.\)]\s+[A-Za-z]", s))

    @staticmethod
    def _is_markdown_heading(line: str) -> bool:
        """Detects markdown headers (# Heading, ## Heading, etc.)."""
        s = line.strip()
        return bool(re.match(r"^#{1,6}\s+[A-Za-z]", s))

    @staticmethod
    def _is_standalone_topic(line: str) -> bool:
        """Detects concise unnumbered topic titles like 'Type conversion' or 'Inheritance'."""
        s = line.strip()
        if not s or len(s) > 60:
            return False
        if re.match(r"^(?:Python A to Z Notes.*|Page \d+|\d+|http.*)$", s, re.IGNORECASE):
            return False
        if any(c in s for c in ["=", "(", ")", "[", "]", "{", "}", "\"", "'", "<", ">", "+", "*", ";", "\\"]):
            return False
        if any(k in s.lower() for k in ["def ", "class ", "import ", "from ", "return ", "print", "raise ", "with "]):
            return False
        if s.endswith((".", ",", ":", ";", "?", "!")):
            return False
        if re.match(r"^O\(.+\)$", s):
            return False
        if s.startswith(("-", "*", "\x7f", "#")):
            return False
        if not re.match(r"^[A-Z][A-Za-z0-9\s/&'\-]+$", s):
            return False
        words = s.split()
        return 1 <= len(words) <= 6

    def _split_unit_into_sections(
        self,
        text: str,
        default_title: str | None,
        source_filename: str,
    ) -> list[tuple[str, str, int]]:
        """Splits a structural unit into semantic sections respecting numbered and topic boundaries."""
        is_markdown = source_filename.lower().endswith((".md", ".markdown"))
        lines = text.split("\n")
        sections: list[tuple[str, list[str], int]] = []

        current_title = default_title or "General"
        current_lines: list[str] = []
        running_offset = 0
        section_start_offset = 0
        in_numbered_section = False
        saw_first_heading = False
        current_sec_num: int | None = None

        for line in lines:
            line_len = len(line) + 1  # newline length
            stripped = line.strip()

            # Ignore running page header/footer markers
            if re.match(r"^(?:Python A to Z Notes.*|Page \d+)$", stripped, re.IGNORECASE):
                running_offset += line_len
                continue

            # Bullet check: lines starting with bullet characters are list items, not top-level section headers
            is_bullet = stripped.startswith(("\x7f", "•", "-", "*"))
            is_num = False
            matched_sec_num: int | None = None
            if not is_bullet:
                m = re.match(r"^(\d+)[\.\)]\s+[A-Za-z]", stripped)
                if m and not stripped.endswith((".", ";", "?", "!")):
                    num = int(m.group(1))
                    # Top-level section number: must increase or be the first numbered section
                    # Sub-lists restarting from 1 (e.g. stages 1..7 inside section 33) stay within the parent section
                    if current_sec_num is None or num > current_sec_num:
                        is_num = True
                        matched_sec_num = num

            is_md = is_markdown and self._is_markdown_heading(line)
            content_str = "\n".join(current_lines).strip()
            # Standalone topics only start a new section if current accumulated content is substantive
            is_topic = (
                not in_numbered_section
                and len(content_str) >= 150
                and self._is_standalone_topic(line)
            )

            if is_num or is_md or is_topic:
                if content_str and len(content_str) >= self.min_chunk_length:
                    sections.append((current_title, current_lines, section_start_offset))
                    current_lines = []
                    section_start_offset = running_offset

                current_title = stripped.lstrip("#").strip()
                in_numbered_section = is_num
                current_sec_num = matched_sec_num if is_num else None
                saw_first_heading = True
                current_lines.append(line)
            else:
                if not saw_first_heading and not current_lines and stripped:
                    if self._is_standalone_topic(line):
                        current_title = stripped
                        saw_first_heading = True
                    else:
                        current_title = default_title or "General"
                current_lines.append(line)

            running_offset += line_len

        if current_lines:
            content_str = "\n".join(current_lines).strip()
            if content_str and len(content_str) >= self.min_chunk_length:
                sections.append((current_title, current_lines, section_start_offset))

        results: list[tuple[str, str, int]] = []
        for title, s_lines, s_offset in sections:
            s_text = "\n".join(s_lines).strip()
            if len(s_text) >= self.min_chunk_length:
                results.append((title, s_text, s_offset))

        if not results and len(text.strip()) >= self.min_chunk_length:
            return [(default_title or "General", text.strip(), 0)]

        return results

    def _chunk_unit(
        self,
        unit: ParsedUnit,
        start_global_offset: int,
        start_chunk_idx: int,
        document_id: str,
        document_version_id: str | None,
        source_filename: str,
    ) -> list[ChunkResult]:
        """Chunks a structural unit (e.g. page) by detecting topic boundaries before falling back to character limits."""
        text = unit.text.strip()
        if len(text) < self.min_chunk_length:
            return []

        sections = self._split_unit_into_sections(
            text=text,
            default_title=unit.section_title,
            source_filename=source_filename,
        )

        results: list[ChunkResult] = []
        curr_idx = start_chunk_idx

        for sec_title, sec_text, rel_offset in sections:
            sec_len = len(sec_text)
            sec_global_offset = start_global_offset + rel_offset

            if sec_len <= self.chunk_char_size:
                token_count = self.estimate_tokens(sec_text)
                results.append(
                    ChunkResult(
                        content=sec_text,
                        chunk_index=curr_idx,
                        page_number=unit.page_number,
                        section_title=sec_title,
                        token_count=token_count,
                        character_count=sec_len,
                        start_offset=sec_global_offset,
                        end_offset=sec_global_offset + sec_len,
                        metadata={
                            "document_id": document_id,
                            "document_version_id": document_version_id,
                            "chunk_index": curr_idx,
                            "page_number": unit.page_number,
                            "section_title": sec_title,
                            "source_filename": source_filename,
                            **unit.metadata,
                        },
                    )
                )
                curr_idx += 1
            else:
                sub_chunks = self._chunk_large_section(
                    sec_text=sec_text,
                    sec_title=sec_title,
                    page_number=unit.page_number,
                    start_global_offset=sec_global_offset,
                    start_chunk_idx=curr_idx,
                    document_id=document_id,
                    document_version_id=document_version_id,
                    source_filename=source_filename,
                    unit_metadata=unit.metadata,
                )
                results.extend(sub_chunks)
                curr_idx += len(sub_chunks)

        return results

    def _chunk_large_section(
        self,
        sec_text: str,
        sec_title: str,
        page_number: int | None,
        start_global_offset: int,
        start_chunk_idx: int,
        document_id: str,
        document_version_id: str | None,
        source_filename: str,
        unit_metadata: dict,
    ) -> list[ChunkResult]:
        """Subdivides an oversized section using sentence/paragraph boundaries with overlap."""
        pieces = self._split_into_pieces(sec_text)
        results: list[ChunkResult] = []
        curr_pieces: list[str] = []
        curr_len = 0
        unit_offset = 0
        curr_idx = start_chunk_idx

        for piece in pieces:
            piece_len = len(piece)
            if curr_len + piece_len > self.chunk_char_size and curr_pieces:
                chunk_str = "".join(curr_pieces).strip()
                if len(chunk_str) >= self.min_chunk_length:
                    start_off = start_global_offset + unit_offset
                    end_off = start_off + len(chunk_str)
                    results.append(
                        ChunkResult(
                            content=chunk_str,
                            chunk_index=curr_idx,
                            page_number=page_number,
                            section_title=sec_title,
                            token_count=self.estimate_tokens(chunk_str),
                            character_count=len(chunk_str),
                            start_offset=start_off,
                            end_offset=end_off,
                            metadata={
                                "document_id": document_id,
                                "document_version_id": document_version_id,
                                "chunk_index": curr_idx,
                                "page_number": page_number,
                                "section_title": sec_title,
                                "source_filename": source_filename,
                                **(unit_metadata or {}),
                            },
                        )
                    )
                    curr_idx += 1

                overlap_pieces: list[str] = []
                overlap_len = 0
                for prev in reversed(curr_pieces):
                    if overlap_len + len(prev) <= self.overlap_char_size:
                        overlap_pieces.insert(0, prev)
                        overlap_len += len(prev)
                    else:
                        break

                unit_offset += len(chunk_str) - overlap_len
                curr_pieces = overlap_pieces
                curr_len = overlap_len

            curr_pieces.append(piece)
            curr_len += piece_len

        if curr_pieces:
            chunk_str = "".join(curr_pieces).strip()
            if len(chunk_str) >= self.min_chunk_length:
                start_off = start_global_offset + unit_offset
                end_off = start_off + len(chunk_str)
                results.append(
                    ChunkResult(
                        content=chunk_str,
                        chunk_index=curr_idx,
                        page_number=page_number,
                        section_title=sec_title,
                        token_count=self.estimate_tokens(chunk_str),
                        character_count=len(chunk_str),
                        start_offset=start_off,
                        end_offset=end_off,
                        metadata={
                            "document_id": document_id,
                            "document_version_id": document_version_id,
                            "chunk_index": curr_idx,
                            "page_number": page_number,
                            "section_title": sec_title,
                            "source_filename": source_filename,
                            **(unit_metadata or {}),
                        },
                    )
                )

        return results

    def _split_into_pieces(self, text: str) -> list[str]:
        """Splits text into fine-grained sentences or whitespace-delimited blocks."""
        # Split keeping delimiters
        parts = re.split(r"(\n\n|\n|\. |\? |! )", text)
        pieces = []
        i = 0
        while i < len(parts):
            chunk = parts[i]
            if i + 1 < len(parts):
                chunk += parts[i + 1]
                i += 2
            else:
                i += 1
            if chunk:
                pieces.append(chunk)
        return pieces if pieces else [text]
