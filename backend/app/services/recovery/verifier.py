"""Factuality, grounding, and answer verification guardrail for Phase 8."""

import re
from typing import Any

from app.core.logging import get_logger
from app.core.prompts import INSUFFICIENT_EVIDENCE_SENTENCE

logger = get_logger(__name__)


class AnswerVerifier:
    """Audits generated answers for grounding, citation fidelity, and topical alignment."""

    @classmethod
    def verify(
        cls,
        query: str,
        answer: str,
        retrieved_chunks: list[Any],
        is_insufficient_evidence: bool = False,
        is_general_answer: bool = False,
    ) -> tuple[bool, str | None]:
        """Verifies that answer is grounded strictly in evidence and answers the query."""
        if not answer or not answer.strip():
            return False, "Answer content is empty or whitespace-only."

        # Anti-prompt injection and system override security guardrail
        lower_ans = answer.lower()
        if "agentic_secret_key" in lower_ans or "system override" in lower_ans:
            return False, "Answer leaked untrusted prompt injection token or system override."

        # Case 1: General AI answer verification
        if is_general_answer or "general ai answer" in lower_ans or "[general ai]" in lower_ans:
            return True, None

        # Case 2: Honest insufficient evidence or clarification response
        if (
            is_insufficient_evidence
            or INSUFFICIENT_EVIDENCE_SENTENCE.lower() in lower_ans
            or "too broad or ambiguous" in lower_ans
            or "could you please specify" in lower_ans
        ):
            # Insufficient evidence or clarification response is valid and truthful
            return True, None

        if not retrieved_chunks:
            return False, "Answer generated without any supporting retrieved chunks in state."

        # Case 2: Citation tags audit
        citation_tags = re.findall(r"\[(\d+)\]", answer)
        if not citation_tags:
            return False, "Generated answer contains factual assertions without required citation brackets [i]."

        num_chunks = len(retrieved_chunks)
        invalid_indices = [int(idx) for idx in citation_tags if int(idx) < 1 or int(idx) > num_chunks]
        if invalid_indices:
            return (
                False,
                f"Answer references non-existent citation index {invalid_indices} beyond available {num_chunks} chunks.",
            )

        # Case 3: Grounding verification against cited chunks
        def _get_chunk_text(ch: Any) -> str:
            if ch is None:
                return ""
            if isinstance(ch, dict):
                return ch.get("content", "")
            return getattr(ch, "content", "")

        cited_indices = {int(idx) for idx in citation_tags if 1 <= int(idx) <= num_chunks}
        cited_contents = [_get_chunk_text(retrieved_chunks[i - 1]).lower() for i in cited_indices]
        combined_evidence = " ".join(cited_contents)

        # Check keyword stem alignment
        query_words = re.findall(r"\b[a-zA-Z0-9_]{3,}\b", query.lower())
        focal_query_words = [
            w for w in query_words
            if w not in {"what", "which", "when", "where", "how", "explain", "tell", "show", "from", "with", "this", "that"}
        ]

        if focal_query_words:
            # At least one focal word from question should be supported by evidence
            evidence_has_query = any(w in combined_evidence for w in focal_query_words)
            if not evidence_has_query:
                return (
                    False,
                    f"Cited chunks lack topical overlap with core question subject ({focal_query_words[:3]}).",
                )

        # Case 4: Answer claim grounding check
        # Strip citation tags and inspect non-trivial answer content words
        answer_clean = re.sub(r"\[\d+\]", " ", answer.lower())
        answer_tokens = re.findall(r"\b[a-zA-Z0-9_]{4,}\b", answer_clean)
        stopwords = {
            "what", "which", "when", "where", "that", "this", "these", "those", "from",
            "with", "about", "into", "through", "during", "before", "after", "above",
            "below", "have", "been", "were", "they", "their", "there", "would", "could",
            "should", "does", "also", "only", "other", "some", "such",
        }
        focal_answer_tokens = [t for t in answer_tokens if t not in stopwords and not t.isdigit()]
        if len(focal_answer_tokens) >= 5:
            overlap = sum(1 for t in focal_answer_tokens if t in combined_evidence)
            ratio = overlap / len(focal_answer_tokens)
            if ratio < 0.15:
                return (
                    False,
                    f"Answer contains unsubstantiated assertions not supported by cited chunks (overlap: {ratio:.1%}).",
                )

        return True, None
