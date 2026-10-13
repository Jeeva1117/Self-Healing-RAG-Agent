"""Intent-preserving query rewriter for self-healing retrieval recovery."""

import re

from app.core.logging import get_logger

logger = get_logger(__name__)

# Common conversational noise prefixes to prune
CONVERSATIONAL_PREFIXES = [
    r"^can you please (?:tell|explain|show)(?:\s+me)?\s+",
    r"^can you (?:tell|explain|show)(?:\s+me)?\s+",
    r"^could you please (?:tell|explain|show)(?:\s+me)?\s+",
    r"^could you (?:tell|explain|show)(?:\s+me)?\s+",
    r"^please (?:tell|explain|show)(?:\s+me)?\s+",
    r"^i would like to know\s+",
    r"^i want to know\s+",
    r"^what can you tell me about\s+",
    r"^give me details on\s+",
    r"^tell me about\s+",
    r"^explain to me\s+",
    r"^explain\s+",
]

# Targeted domain expansions for programming concepts
DOMAIN_EXPANSIONS = {
    "operator": "arithmetic comparison logical operators expression",
    "operators": "arithmetic comparison logical operators expression",
    "function": "def parameters return values arguments functions",
    "functions": "def parameters return values arguments functions",
    "loop": "for while loop iteration break continue",
    "loops": "for while loop iteration break continue",
    "collection": "lists tuples dictionaries sets collections",
    "collections": "lists tuples dictionaries sets collections",
    "dictionary": "dict key value hashing dictionary",
    "dictionaries": "dict key value hashing dictionary",
    "exception": "try except raise exception error handling",
    "exceptions": "try except raise exception error handling",
    "class": "object oriented programming class method inheritance",
    "classes": "object oriented programming class method inheritance",
    "variable": "variables assignment data types declaration",
    "variables": "variables assignment data types declaration",
}


class QueryRewriter:
    """Reformulates search queries to improve recall while strictly preserving user intent."""

    @classmethod
    def rewrite(
        cls,
        original_query: str,
        query_history: list[str] | None = None,
        extracted_terms: list[str] | None = None,
    ) -> str:
        """Rewrites search query by stripping noise, focusing core terms, and adding domain synonyms."""
        history = set(query_history or [])
        clean = original_query.strip()

        # 1. Strip conversational filler
        for pat in CONVERSATIONAL_PREFIXES:
            clean = re.sub(pat, "", clean, flags=re.IGNORECASE).strip()

        # Remove trailing question marks and punctuation
        clean = clean.rstrip("?!.,;:")

        # 2. Check domain expansion
        words = re.findall(r"\b[a-zA-Z0-9_]+\b", clean.lower())
        expansions = []
        for w in words:
            if w in DOMAIN_EXPANSIONS:
                expansions.append(DOMAIN_EXPANSIONS[w])

        # Candidate 1: Cleaned query with key domain expansion
        if expansions:
            exp_terms = " ".join(expansions[:1])
            cand_1 = f"{clean} {exp_terms}".strip()
            if cand_1.lower() not in history and cand_1.lower() != original_query.lower():
                return cand_1

        # Candidate 2: Cleaned query without noise
        if clean.lower() not in history and clean.lower() != original_query.lower():
            return clean

        # Candidate 3: Extracted search terms concatenation
        if extracted_terms:
            cand_3 = " ".join(extracted_terms)
            if cand_3.lower() not in history and cand_3.lower() != original_query.lower():
                return cand_3

        # Candidate 4: Focused topic query
        cand_4 = f"{clean} overview documentation"
        if cand_4.lower() not in history:
            return cand_4

        return clean
