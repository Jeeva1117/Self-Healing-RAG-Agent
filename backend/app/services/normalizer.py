"""Text normalization service preserving structural elements and clean UTF-8."""

import re
import unicodedata

# Remove null bytes and non-printable control characters, but preserve tabs, newlines, carriage returns
CONTROL_CHARS_REGEX = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")
# Collapse 3 or more consecutive newlines into 2 (paragraphs)
EXCESSIVE_NEWLINES_REGEX = re.compile(r"\n{3,}")
# Collapse multiple horizontal spaces/tabs on a single line without joining lines
HORIZONTAL_WHITESPACE_REGEX = re.compile(r"[^\S\r\n]{2,}")


class TextNormalizer:
    """Normalizes raw text cleanly without altering markdown, code, bullet lists, or tables."""

    @staticmethod
    def normalize(text: str) -> str:
        """Normalizes extracted text cleanly.

        Steps:
        1. Unicode normalization (NFC).
        2. Strip null and illegal ASCII control characters.
        3. Normalize Windows CRLF (\r\n) and classic Mac CR (\r) to standard LF (\n).
        4. Collapse multiple spaces within a line without collapsing line breaks.
        5. Collapse 3+ consecutive newlines to at most 2 newlines (paragraph separator).
        6. Strip leading and trailing whitespace.
        """
        if not text:
            return ""

        # 1. Unicode NFC
        text = unicodedata.normalize("NFC", text)

        # 2. Control characters removal
        text = CONTROL_CHARS_REGEX.sub("", text)

        # 3. Line endings
        text = text.replace("\r\n", "\n").replace("\r", "\n")

        # 4. Collapse runs of horizontal spaces (spaces & tabs)
        lines = []
        for line in text.split("\n"):
            # Collapse multiple spaces within the line
            collapsed = HORIZONTAL_WHITESPACE_REGEX.sub(" ", line)
            lines.append(collapsed.rstrip())
        text = "\n".join(lines)

        # 5. Collapse excessive blank lines
        text = EXCESSIVE_NEWLINES_REGEX.sub("\n\n", text)

        return text.strip()
