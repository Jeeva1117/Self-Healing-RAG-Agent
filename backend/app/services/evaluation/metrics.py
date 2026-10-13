"""Precise, reproducible mathematical metrics for Phase 9 RAG evaluation."""

import math
import re
from typing import Any

from app.core.prompts import INSUFFICIENT_EVIDENCE_SENTENCE


def compute_precision_at_k(
    retrieved_ids: list[Any],
    relevant_ids: set[Any],
    k: int,
) -> float | None:
    """Computes Precision@K: fraction of retrieved items in top-K that are relevant.

    Returns None if relevant_ids is empty (does not penalize missing ground-truth labels).
    """
    if not relevant_ids:
        return None
    if k <= 0:
        return 0.0
    top_k = retrieved_ids[:k]
    hits = sum(1 for item in top_k if item in relevant_ids)
    return hits / k


def compute_recall_at_k(
    retrieved_ids: list[Any],
    relevant_ids: set[Any],
    k: int,
) -> float | None:
    """Computes Recall@K: fraction of relevant items found in top-K.

    Returns None if relevant_ids is empty.
    """
    if not relevant_ids:
        return None
    if k <= 0:
        return 0.0
    top_k = retrieved_ids[:k]
    hits = sum(1 for item in top_k if item in relevant_ids)
    return hits / len(relevant_ids)


def compute_reciprocal_rank(
    retrieved_ids: list[Any],
    relevant_ids: set[Any],
) -> float | None:
    """Computes Reciprocal Rank (RR): 1 / rank of first relevant retrieved item.

    Returns None if relevant_ids is empty; 0.0 if no relevant items retrieved.
    """
    if not relevant_ids:
        return None
    for rank, item in enumerate(retrieved_ids, start=1):
        if item in relevant_ids:
            return 1.0 / rank
    return 0.0


def compute_ndcg_at_k(
    retrieved_ids: list[Any],
    relevant_ids: set[Any],
    k: int,
) -> float | None:
    """Computes Normalized Discounted Cumulative Gain at K (nDCG@K).

    Handles binary relevance labels. Returns None if relevant_ids is empty.
    """
    if not relevant_ids or k <= 0:
        return None

    top_k = retrieved_ids[:k]
    dcg = 0.0
    for rank, item in enumerate(top_k, start=1):
        rel = 1.0 if item in relevant_ids else 0.0
        dcg += rel / math.log2(rank + 1)

    ideal_hits = min(k, len(relevant_ids))
    if ideal_hits == 0:
        return 0.0

    idcg = sum(1.0 / math.log2(r + 1) for r in range(1, ideal_hits + 1))
    if idcg <= 0.0:
        return 0.0

    return dcg / idcg


def compute_chunk_coverage(
    retrieved_ids: list[Any],
    relevant_ids: set[Any],
) -> float | None:
    """Computes total fraction of expected chunks retrieved across all returned items."""
    if not relevant_ids:
        return None
    found = sum(1 for item in relevant_ids if item in set(retrieved_ids))
    return found / len(relevant_ids)


def compute_key_fact_coverage(
    answer: str,
    expected_key_facts: list[str],
) -> float:
    """Measures fraction of required key facts present in generated response."""
    if not expected_key_facts:
        return 1.0
    ans_lower = answer.lower()
    matches = sum(1 for fact in expected_key_facts if fact.lower() in ans_lower)
    return matches / len(expected_key_facts)


def compute_citation_validity(
    answer: str,
    num_chunks: int,
) -> tuple[float, int, int]:
    """Audits bracketed citation IDs [i] for bounds correctness against available chunks.

    Returns:
        (validity_ratio, valid_citations_count, total_citations_count)
    """
    tags = re.findall(r"\[(\d+)\]", answer)
    if not tags:
        return 1.0, 0, 0
    valid_count = sum(1 for t in tags if 1 <= int(t) <= num_chunks)
    return valid_count / len(tags), valid_count, len(tags)


def compute_groundedness(
    answer: str,
    retrieved_chunks: list[Any],
    is_insufficient_evidence: bool = False,
) -> float:
    """Calculates factual grounding ratio of non-trivial answer content against retrieved evidence.

    Truthful insufficient-evidence answers receive a faithful score of 1.0.
    """
    if is_insufficient_evidence or INSUFFICIENT_EVIDENCE_SENTENCE.lower() in answer.lower():
        return 1.0

    if not retrieved_chunks:
        return 0.0

    def get_text(ch: Any) -> str:
        if ch is None:
            return ""
        if isinstance(ch, dict):
            return ch.get("snippet") or ch.get("content") or ch.get("excerpt") or ""
        return getattr(ch, "snippet", None) or getattr(ch, "content", None) or getattr(ch, "excerpt", "") or ""

    combined_evidence = " ".join(get_text(c).lower() for c in retrieved_chunks)
    if not combined_evidence.strip():
        return 0.0

    # Prune citation tags and extract focal content tokens
    clean = re.sub(r"\[\d+\]", " ", answer.lower())
    tokens = re.findall(r"\b[a-zA-Z0-9_]{4,}\b", clean)
    stopwords = {
        "what",
        "which",
        "when",
        "where",
        "that",
        "this",
        "these",
        "those",
        "from",
        "with",
        "about",
        "into",
        "through",
        "during",
        "before",
        "after",
        "above",
        "below",
        "have",
        "been",
        "were",
        "they",
        "their",
        "there",
        "would",
        "could",
        "should",
        "does",
        "also",
        "only",
        "other",
        "some",
        "such",
        "than",
        "then",
    }
    focal_tokens = [t for t in tokens if t not in stopwords and not t.isdigit()]
    if not focal_tokens:
        return 1.0

    grounded_count = sum(1 for t in focal_tokens if t in combined_evidence)
    return min(1.0, grounded_count / len(focal_tokens))


def compute_answer_relevance(
    query: str,
    answer: str,
    is_insufficient_evidence: bool = False,
) -> float:
    """Calculates topical alignment between user inquiry and synthesized response."""
    if is_insufficient_evidence:
        return 1.0

    q_words = re.findall(r"\b[a-zA-Z0-9_]{3,}\b", query.lower())
    focal_q = [
        w
        for w in q_words
        if w not in {"what", "which", "when", "where", "how", "explain", "tell", "show", "from", "with", "this", "that"}
    ]
    if not focal_q:
        return 1.0

    ans_lower = answer.lower()
    matches = sum(1 for w in focal_q if w in ans_lower)
    return min(1.0, matches / len(focal_q))
