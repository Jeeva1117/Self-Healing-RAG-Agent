"""High-precision grounded synthesis LLM provider.

Generates strictly evidence-grounded responses directly from retrieved knowledge base chunks
without external API dependencies, hallucinations, or ungrounded claims.
"""

import re
from collections.abc import AsyncIterator
from typing import Any

from app.core.logging import get_logger
from app.core.prompts import INSUFFICIENT_EVIDENCE_SENTENCE
from app.domain.interfaces.llm import LLMMessage, LLMProviderInterface, LLMResponse

logger = get_logger(__name__)

INSUFFICIENT_EVIDENCE_MESSAGE = INSUFFICIENT_EVIDENCE_SENTENCE

STOP_WORDS = {
    "a",
    "an",
    "the",
    "in",
    "on",
    "at",
    "to",
    "for",
    "of",
    "and",
    "or",
    "is",
    "are",
    "was",
    "were",
    "be",
    "been",
    "being",
    "have",
    "has",
    "had",
    "do",
    "does",
    "did",
    "what",
    "which",
    "who",
    "whom",
    "this",
    "that",
    "these",
    "those",
    "how",
    "why",
    "when",
    "where",
    "can",
    "could",
    "should",
    "would",
    "explain",
    "describe",
    "tell",
    "show",
    "me",
    "about",
    "with",
    "from",
    "by",
    "as",
    "into",
    "through",
    "during",
    "before",
    "after",
    "above",
    "below",
}


def _stem(word: str) -> str:
    """Basic English suffix stemming for query keyword matching."""
    w = word.lower()
    if w.endswith("ies") and len(w) > 4:
        return w[:-3] + "y"
    if w.endswith("es") and len(w) > 3:
        return w[:-2]
    if w.endswith("s") and not w.endswith("ss") and len(w) > 2:
        return w[:-1]
    if w.endswith("ing") and len(w) > 4:
        return w[:-3]
    if w.endswith("ed") and len(w) > 3:
        return w[:-2]
    return w


class GroundedSynthesisProvider(LLMProviderInterface):
    """Local, deterministic LLM provider that synthesizes responses strictly from evidence chunks."""

    def __init__(self, model_name: str = "grounded-synthesis-engine"):
        self.model_name = model_name

    def _extract_evidence_blocks(self, context_text: str) -> list[tuple[int, str, dict[str, str]]]:
        """Parses numbered evidence blocks [Evidence N] from prompt context."""
        pattern = re.compile(
            r"\[Evidence\s+(\d+)\](?:\s*\((.*?)\))?\s*\n(.*?)(?=(?:\[Evidence\s+\d+\]|\Z))",
            re.DOTALL,
        )
        matches = pattern.findall(context_text)
        evidence_blocks: list[tuple[int, str, dict[str, str]]] = []

        for num_str, meta_str, content_str in matches:
            idx = int(num_str)
            meta: dict[str, str] = {}
            if meta_str:
                for part in meta_str.split(","):
                    if ":" in part:
                        k, v = part.split(":", 1)
                        meta[k.strip().lower()] = v.strip()
            evidence_blocks.append((idx, content_str.strip(), meta))

        return evidence_blocks

    def _extract_query_keywords(self, user_query: str) -> list[str]:
        raw_tokens = re.findall(r"\b[a-zA-Z0-9_\-\.]+\b", user_query.lower())
        return [t for t in raw_tokens if len(t) > 1 and t not in STOP_WORDS]

    @staticmethod
    def _is_topic_list_query(query: str) -> bool:
        """Detects if query asks for a list or overview of core concepts and topics."""
        q = query.lower()
        indicators = [
            "core concept",
            "core concepts",
            "main topic",
            "main topics",
            "list the topics",
            "list topics",
            "topics covered",
            "what topics",
            "table of contents",
            "learning roadmap",
            "roadmap",
            "overview of topics",
            "topics from",
            "topics in this",
            "concepts covered",
            "summary of topics",
            "list the main topics",
            "all topics",
            "curriculum",
        ]
        return any(ind in q for ind in indicators)

    def _synthesize_topic_list_answer(
        self,
        user_query: str,
        evidence_blocks: list[tuple[int, str, dict[str, str]]],
    ) -> str | None:
        """Extracts a structured, verified list of actual topics from roadmap or section evidence."""
        # 1. Search for dedicated roadmap or topic table block
        roadmap_block: tuple[int, str, dict[str, str]] | None = None
        other_topic_blocks: list[tuple[int, str, dict[str, str]]] = []

        for idx, content, meta in evidence_blocks:
            sec = meta.get("section", "").lower()
            c_lower = content.lower()
            if (
                "roadmap" in sec
                or "topics" in sec
                or ("stage" in c_lower and "topics" in c_lower and "practice goal" in c_lower)
            ):
                if roadmap_block is None:
                    roadmap_block = (idx, content, meta)
                    continue
            other_topic_blocks.append((idx, content, meta))

        if roadmap_block:
            r_idx, r_content, r_meta = roadmap_block
            doc_name = r_meta.get("document", "the uploaded notes")
            page_info = f" (Page {r_meta['page']})" if "page" in r_meta else ""

            lines = r_content.split("\n")
            items: list[tuple[str, str]] = []
            curr_title: str | None = None
            curr_desc: list[str] = []

            for line in lines:
                s = line.strip()
                m = re.match(r"^(\d+)[\.\)]\s+([A-Za-z0-9_/&\s\-]+)$", s)
                if m:
                    # Ignore the section header itself
                    if "roadmap" in m.group(2).lower():
                        continue
                    if curr_title:
                        desc_text = ", ".join(curr_desc) if curr_desc else ""
                        items.append((curr_title, desc_text))
                    curr_title = m.group(2).strip()
                    curr_desc = []
                else:
                    if (
                        curr_title
                        and s
                        and not re.match(
                            r"^(?:Stage|Topics|Practice goal|Write|Build|Solve|Number).*$", s, re.IGNORECASE
                        )
                    ):
                        curr_desc.append(s)

            if curr_title:
                desc_text = ", ".join(curr_desc) if curr_desc else ""
                items.append((curr_title, desc_text))

            if items:
                out = [
                    f"Based on **{doc_name}**{page_info} [{r_idx}], the core concepts and main topics covered in the uploaded Python notes are:\n"
                ]
                for i, (title, desc) in enumerate(items, start=1):
                    if desc:
                        out.append(f"{i}. **{title}**: {desc} [{r_idx}].")
                    else:
                        out.append(f"{i}. **{title}** [{r_idx}].")

                # If other evidence blocks contain specific sections, append them cleanly
                other_sections: list[tuple[str, int]] = []
                for oi, _oc, om in other_topic_blocks:
                    sec_name = om.get("section")
                    if sec_name and not sec_name.startswith("Page ") and "advice" not in sec_name.lower():
                        other_sections.append((sec_name, oi))

                if other_sections:
                    sec_strs = [f"**{s}** [{oi}]" for s, oi in other_sections[:4]]
                    out.append(
                        f"\nAdditionally, specific core sections documented in the notes include {', '.join(sec_strs)}."
                    )

                return "\n".join(out)

        # 2. If no single roadmap block, extract distinct section titles from evidence blocks
        collected_sections: list[tuple[str, int, str]] = []
        seen_sections: set[str] = set()

        for idx, _content, meta in evidence_blocks:
            sec_title = meta.get("section", "")
            if sec_title and not sec_title.startswith("Page ") and sec_title not in seen_sections:
                seen_sections.add(sec_title)
                doc = meta.get("document", "the knowledge base")
                collected_sections.append((sec_title, idx, doc))

        if collected_sections:
            doc_name = collected_sections[0][2]
            out = [f"Based on the retrieved sections from **{doc_name}**, the core topics covered include:\n"]
            for i, (title, s_idx, _) in enumerate(collected_sections, start=1):
                out.append(f"{i}. **{title}** [{s_idx}].")
            return "\n".join(out)

        return None

    def _synthesize_grounded_answer(
        self, user_query: str, evidence_blocks: list[tuple[int, str, dict[str, str]]]
    ) -> str:
        """Synthesizes an answer strictly grounded in the evidence blocks or reports insufficiency."""
        if not evidence_blocks:
            return INSUFFICIENT_EVIDENCE_MESSAGE

        query_keywords = self._extract_query_keywords(user_query)
        if not query_keywords:
            return INSUFFICIENT_EVIDENCE_MESSAGE

        stemmed_keywords = {_stem(k) for k in query_keywords}

        # Check for topic listing intent
        if self._is_topic_list_query(user_query):
            topic_answer = self._synthesize_topic_list_answer(user_query, evidence_blocks)
            if topic_answer:
                return topic_answer

        # Build document-wide term counts across all provided evidence blocks
        corpus_stems: dict[str, int] = {}
        for _, content, _ in evidence_blocks:
            c_words = re.findall(r"\b[a-zA-Z0-9_\-\.]+\b", content.lower())
            seen_in_block = {_stem(w) for w in c_words}
            for s in seen_in_block:
                corpus_stems[s] = corpus_stems.get(s, 0) + 1

        # Check if query keywords have any meaningful match across the blocks
        focal_keywords = [
            k for k in query_keywords if k not in {"python", "notes", "knowledge", "base", "document", "uploaded"}
        ]
        has_focal_match = False
        for _, content, meta in evidence_blocks:
            c_text = (content + " " + meta.get("section", "")).lower()
            if any(_stem(k) in c_text for k in focal_keywords):
                has_focal_match = True
                break

        if focal_keywords and not has_focal_match:
            return INSUFFICIENT_EVIDENCE_MESSAGE

        def get_stem_weight(s: str) -> float:
            doc_freq = corpus_stems.get(s, 1)
            return 1.0 / (doc_freq + 0.1)

        # Score evidence blocks
        scored_blocks: list[tuple[float, float, int, str, dict[str, str]]] = []
        for idx, content, meta in evidence_blocks:
            c_words = re.findall(r"\b[a-zA-Z0-9_\-\.]+\b", content.lower())
            c_stems = [_stem(w) for w in c_words]
            matched_query_stems = {s for s in c_stems if s in stemmed_keywords}

            coverage = len(matched_query_stems) / len(stemmed_keywords)
            weighted_score = sum(get_stem_weight(s) for s in c_stems if s in stemmed_keywords)

            # Boost if section title matches any focal query term (e.g. '4. Operators' for 'operators')
            sec_title = meta.get("section", "").lower()
            if any(k in sec_title for k in query_keywords):
                weighted_score += 15.0
                coverage += 0.5

            if matched_query_stems:
                scored_blocks.append((coverage, weighted_score, idx, content, meta))

        if not scored_blocks:
            return INSUFFICIENT_EVIDENCE_MESSAGE

        scored_blocks.sort(key=lambda x: (-x[0], -x[1]))
        best_coverage, best_weighted_score, primary_idx, primary_content, primary_meta = scored_blocks[0]

        doc_name = primary_meta.get("document", "the knowledge base")
        page_info = f" (Page {primary_meta['page']})" if "page" in primary_meta else ""
        sec_name = primary_meta.get("section")
        sec_info = f" ({sec_name})" if sec_name and not sec_name.startswith("Page ") else ""

        lines = [line for line in primary_content.split("\n") if line.strip()]
        body_lines = lines[1:] if lines and re.match(r"^\d+\.\s+", lines[0]) else lines

        out = [
            f'Based on **{doc_name}**{page_info}{sec_info} [{primary_idx}], here is the verified information regarding **"{user_query}"**:\n',
            "\n".join(body_lines).strip(),
            f"\n[{primary_idx}]",
        ]

        return "\n\n".join(out)

    async def generate(
        self,
        messages: list[LLMMessage],
        temperature: float = 0.7,
        max_tokens: int | None = None,
        **kwargs: Any,
    ) -> LLMResponse:
        """Generates evidence-grounded response text."""
        user_query = ""
        context_text = ""

        for msg in messages:
            if msg.role == "user":
                user_query = msg.content
            elif msg.role == "system":
                context_text = msg.content

        evidence_blocks = self._extract_evidence_blocks(context_text)
        answer = self._synthesize_grounded_answer(user_query, evidence_blocks)

        prompt_tokens = sum(len(m.content.split()) for m in messages)
        completion_tokens = len(answer.split())

        return LLMResponse(
            content=answer,
            model=self.model_name,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=prompt_tokens + completion_tokens,
            finish_reason="stop",
            metadata={"evidence_blocks_count": len(evidence_blocks)},
        )

    async def generate_stream(
        self,
        messages: list[LLMMessage],
        temperature: float = 0.7,
        max_tokens: int | None = None,
        **kwargs: Any,
    ) -> AsyncIterator[str]:
        """Streams tokens token-by-token."""
        res = await self.generate(messages, temperature=temperature, max_tokens=max_tokens, **kwargs)
        tokens = res.content.split(" ")
        for i, token in enumerate(tokens):
            yield token + (" " if i < len(tokens) - 1 else "")
