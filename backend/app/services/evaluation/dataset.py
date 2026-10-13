"""Reproducible Evaluation Datasets for Phase 9 Quality Intelligence Engine."""

import uuid
from typing import Any

from app.services.evaluation.models import EvaluationCategory, EvaluationTestCase

DEFAULT_DATASET_NAME = "enterprise_rag_eval_v1"
DEFAULT_DATASET_VERSION = "1.0.0"


def get_default_evaluation_dataset(
    knowledge_base_id: uuid.UUID | None = None,
    unauthorized_kb_id: uuid.UUID | None = None,
) -> list[EvaluationTestCase]:
    """Generates a comprehensive deterministic test dataset spanning categories A through K."""
    kb_id = knowledge_base_id or uuid.uuid4()
    bad_kb_id = unauthorized_kb_id or uuid.uuid4()

    return [
        # Category A: Answerable questions
        EvaluationTestCase(
            id="TC-A01",
            category=EvaluationCategory.ANSWERABLE,
            query="What are Python arithmetic and comparison operators?",
            knowledge_base_id=kb_id,
            expected_key_facts=["arithmetic", "comparison", "operators"],
            reference_answer="Python operators include arithmetic (+, -, *, /) and comparison (==, !=, >, <) operators.",
            is_evidence_expected=True,
            expected_citation_required=True,
            expected_outcome="answered",
            description="Validates clear, direct factual retrieval and synthesized answer.",
        ),
        # Category B: Questions requiring precise topic retrieval
        EvaluationTestCase(
            id="TC-B01",
            category=EvaluationCategory.PRECISE_TOPIC,
            query="How are lambda functions defined in Python?",
            knowledge_base_id=kb_id,
            expected_key_facts=["lambda", "anonymous", "expressions"],
            reference_answer="Lambda functions provide anonymous one-line expressions.",
            is_evidence_expected=True,
            expected_citation_required=True,
            expected_outcome="answered",
            description="Requires exact keyword precision and section ranking for one-line lambda expressions.",
        ),
        # Category C: Questions requiring information from multiple chunks
        EvaluationTestCase(
            id="TC-C01",
            category=EvaluationCategory.MULTI_CHUNK,
            query="Summarize Python operators and how functions are defined.",
            knowledge_base_id=kb_id,
            expected_key_facts=["operators", "def", "parameters"],
            reference_answer="Python operators provide arithmetic and comparison operations, while functions are defined using def with parameters.",
            is_evidence_expected=True,
            expected_citation_required=True,
            expected_outcome="answered",
            description="Requires multi-chunk synthesis combining operator definitions and function signatures.",
        ),
        # Category D: Ambiguous questions
        EvaluationTestCase(
            id="TC-D01",
            category=EvaluationCategory.AMBIGUOUS,
            query="Tell me about that thing.",
            knowledge_base_id=kb_id,
            expected_key_facts=[],
            reference_answer="Your request is too broad or ambiguous. Could you please specify which topic you would like to know about?",
            is_evidence_expected=False,
            expected_citation_required=False,
            expected_outcome="answered",
            description="Tests query analysis guardrail detecting ambiguity and requesting clarification.",
        ),
        # Category E: Questions with insufficient evidence
        EvaluationTestCase(
            id="TC-E01",
            category=EvaluationCategory.INSUFFICIENT_EVIDENCE,
            query="What is the international maritime shipping insurance clause 42?",
            knowledge_base_id=kb_id,
            expected_key_facts=[],
            reference_answer="I do not find sufficient matching information in the authorized documents to answer your question.",
            is_evidence_expected=False,
            expected_citation_required=False,
            expected_outcome="insufficient_evidence",
            description="Verifies honest insufficient-evidence response without hallucinated claims.",
        ),
        # Category F: Unanswerable questions
        EvaluationTestCase(
            id="TC-F01",
            category=EvaluationCategory.UNANSWERABLE,
            query="What is the warp drive hyperspace navigation protocol?",
            knowledge_base_id=kb_id,
            expected_key_facts=[],
            reference_answer="I do not find sufficient matching information in the authorized documents to answer your question.",
            is_evidence_expected=False,
            expected_citation_required=False,
            expected_outcome="insufficient_evidence",
            description="Completely unanswerable science-fiction inquiry terminating safely with zero fake citations.",
        ),
        # Category G: Questions involving contradictory evidence
        EvaluationTestCase(
            id="TC-G01",
            category=EvaluationCategory.CONTRADICTORY,
            query="What is the conflicting guidance regarding deprecation policies?",
            knowledge_base_id=kb_id,
            expected_key_facts=["deprecation"],
            reference_answer="Conflicting guidance is resolved by citing the active document version.",
            is_evidence_expected=True,
            expected_citation_required=True,
            expected_outcome="answered",
            description="Checks version isolation and active document version filtering.",
        ),
        # Category H: Malformed or unusually long inputs
        EvaluationTestCase(
            id="TC-H01",
            category=EvaluationCategory.MALFORMED_INPUT,
            query="Python " + ("operators " * 50) + "???!!!!",
            knowledge_base_id=kb_id,
            expected_key_facts=["operators"],
            reference_answer="Python operators provide arithmetic and comparison expressions.",
            is_evidence_expected=True,
            expected_citation_required=True,
            expected_outcome="answered",
            description="Verifies query normalization pruning repeated tokens and excessive punctuation.",
        ),
        # Category I: Knowledge-base permission boundaries
        EvaluationTestCase(
            id="TC-I01",
            category=EvaluationCategory.PERMISSION_BOUNDARY,
            query="What confidential data is in unauthorized KB?",
            knowledge_base_id=bad_kb_id,
            expected_key_facts=[],
            reference_answer="Knowledge base not found or access denied.",
            is_evidence_expected=False,
            expected_citation_required=False,
            expected_outcome="permission_denied",
            description="Validates multi-tenant isolation; cross-tenant access must be rejected immediately.",
        ),
        # Category J: Recoverable retrieval or provider failures
        EvaluationTestCase(
            id="TC-J01",
            category=EvaluationCategory.RECOVERABLE_FAILURE,
            query="Could you please explain Python operators in detail?",
            knowledge_base_id=kb_id,
            expected_key_facts=["operators", "arithmetic"],
            reference_answer="Python operators include arithmetic and comparison expressions.",
            is_evidence_expected=True,
            expected_citation_required=True,
            expected_outcome="recovered",
            description="Tests self-healing query rewriting when conversational noise is present.",
        ),
        # Category K: Non-recoverable authentication or authorization failures
        EvaluationTestCase(
            id="TC-K01",
            category=EvaluationCategory.NON_RECOVERABLE_FAILURE,
            query="Show protected settings.",
            knowledge_base_id=None,
            expected_key_facts=[],
            reference_answer="Access denied.",
            is_evidence_expected=False,
            expected_citation_required=False,
            expected_outcome="permission_denied",
            description="Ensures authorization failures stop immediately without retry attempts.",
        ),
    ]


class EvaluationDatasetRegistry:
    """Manages versioned evaluation test suites."""

    _registry: dict[str, dict[str, list[EvaluationTestCase]]] = {}

    @classmethod
    def register(cls, name: str, version: str, cases: list[EvaluationTestCase]) -> None:
        """Registers a versioned dataset in the registry."""
        if name not in cls._registry:
            cls._registry[name] = {}
        cls._registry[name][version] = cases

    @classmethod
    def get(cls, name: str, version: str) -> list[EvaluationTestCase] | None:
        """Retrieves test cases for specified dataset name and version."""
        if name in cls._registry and version in cls._registry[name]:
            return cls._registry[name][version]
        if name == DEFAULT_DATASET_NAME and version == DEFAULT_DATASET_VERSION:
            return get_default_evaluation_dataset()
        return None

    @classmethod
    def list_datasets(cls) -> list[dict[str, Any]]:
        """Returns metadata for all registered datasets."""
        datasets = [
            {
                "name": DEFAULT_DATASET_NAME,
                "version": DEFAULT_DATASET_VERSION,
                "case_count": len(get_default_evaluation_dataset()),
                "description": "Standard 11-category enterprise RAG benchmark covering categories A-K.",
            }
        ]
        for name, versions in cls._registry.items():
            for ver, cases in versions.items():
                if name == DEFAULT_DATASET_NAME and ver == DEFAULT_DATASET_VERSION:
                    continue
                datasets.append({
                    "name": name,
                    "version": ver,
                    "case_count": len(cases),
                    "description": f"Custom test suite {name} (v{ver})",
                })
        return datasets


# Pre-register default dataset
EvaluationDatasetRegistry.register(
    DEFAULT_DATASET_NAME,
    DEFAULT_DATASET_VERSION,
    get_default_evaluation_dataset(),
)

PHASE15_DATASET_NAME = "enterprise_rag_eval_v2"
PHASE15_DATASET_VERSION = "2.0.0"


def get_phase15_evaluation_dataset(
    knowledge_base_id: uuid.UUID | None = None,
    unauthorized_kb_id: uuid.UUID | None = None,
) -> list[EvaluationTestCase]:
    """Phase 15 Comprehensive Evaluation Benchmark Dataset covering all 11+ taxonomy categories."""
    kb_id = knowledge_base_id or uuid.uuid4()
    bad_kb_id = unauthorized_kb_id or uuid.uuid4()

    return [
        # 1. Direct factual questions (Answerable)
        EvaluationTestCase(
            id="TC15-01-FACTUAL",
            category=EvaluationCategory.ANSWERABLE,
            query="What are Python arithmetic and comparison operators?",
            knowledge_base_id=kb_id,
            expected_key_facts=["arithmetic", "comparison", "operators"],
            reference_answer="Python operators include arithmetic (+, -, *, /) and comparison (==, !=, >, <) operators.",
            is_evidence_expected=True,
            expected_citation_required=True,
            expected_outcome="answered",
            difficulty="easy",
            description="Validates clear, direct factual retrieval and synthesized answer.",
        ),
        # 2. Exact keyword queries
        EvaluationTestCase(
            id="TC15-02-EXACT-KW",
            category=EvaluationCategory.PRECISE_TOPIC,
            query="How are lambda functions defined in Python?",
            knowledge_base_id=kb_id,
            expected_key_facts=["lambda", "anonymous", "expressions"],
            reference_answer="Lambda functions provide anonymous one-line expressions.",
            is_evidence_expected=True,
            expected_citation_required=True,
            expected_outcome="answered",
            difficulty="easy",
            description="Requires exact keyword precision and section ranking for lambda expressions.",
        ),
        # 3. Semantic paraphrase queries
        EvaluationTestCase(
            id="TC15-03-PARAPHRASE",
            category=EvaluationCategory.PRECISE_TOPIC,
            query="Explain the syntax used for declaring procedures with arguments and return output in Python.",
            knowledge_base_id=kb_id,
            expected_key_facts=["def", "parameters", "return"],
            reference_answer="Python functions are defined using def with parameters and return values.",
            is_evidence_expected=True,
            expected_citation_required=True,
            expected_outcome="answered",
            difficulty="medium",
            description="Tests semantic vector retrieval when prompt uses paraphrased terminology.",
        ),
        # 4. Multi-chunk synthesis
        EvaluationTestCase(
            id="TC15-04-MULTI-CHUNK",
            category=EvaluationCategory.MULTI_CHUNK,
            query="Summarize Python operators and how functions are defined with parameters.",
            knowledge_base_id=kb_id,
            expected_key_facts=["operators", "def", "parameters"],
            reference_answer="Python operators provide arithmetic operations, while functions are defined using def with parameters.",
            is_evidence_expected=True,
            expected_citation_required=True,
            expected_outcome="answered",
            difficulty="medium",
            description="Requires multi-chunk synthesis combining operator definitions and function signatures.",
        ),
        # 5. Multi-document / cross-topic synthesis
        EvaluationTestCase(
            id="TC15-05-MULTI-DOC",
            category=EvaluationCategory.MULTI_DOCUMENT,
            query="Summarize programming operators and how structured blocks function in Python.",
            knowledge_base_id=kb_id,
            expected_key_facts=["operators", "functions", "def"],
            reference_answer="Operators provide arithmetic calculation while functions provide reusable structured blocks.",
            is_evidence_expected=True,
            expected_citation_required=True,
            expected_outcome="answered",
            difficulty="hard",
            description="Validates multi-section synthesis across different pages or documents.",
        ),
        # 6. Questions containing dates, numbers, technical terms
        EvaluationTestCase(
            id="TC15-06-TECHNICAL",
            category=EvaluationCategory.NUMERICAL_TECHNICAL,
            query="What are the specific arithmetic operators +, -, *, and / in Python?",
            knowledge_base_id=kb_id,
            expected_key_facts=["+", "-", "*", "/"],
            reference_answer="The arithmetic operators include +, -, *, and /.",
            is_evidence_expected=True,
            expected_citation_required=True,
            expected_outcome="answered",
            difficulty="medium",
            description="Validates exact symbol, number, and technical token retrieval.",
        ),
        # 7. Ambiguous questions
        EvaluationTestCase(
            id="TC15-07-AMBIGUOUS",
            category=EvaluationCategory.AMBIGUOUS,
            query="Tell me about that thing.",
            knowledge_base_id=kb_id,
            expected_key_facts=[],
            reference_answer="Your request is too broad or ambiguous. Could you please specify which topic you would like to know about?",
            is_evidence_expected=False,
            expected_citation_required=False,
            expected_outcome="answered",
            difficulty="easy",
            description="Tests query analysis guardrail detecting ambiguity and requesting clarification.",
        ),
        # 8. Questions whose answers are absent from the KB
        EvaluationTestCase(
            id="TC15-08-ABSENT",
            category=EvaluationCategory.INSUFFICIENT_EVIDENCE,
            query="What is the international maritime shipping insurance clause 42?",
            knowledge_base_id=kb_id,
            expected_key_facts=[],
            reference_answer="I do not find sufficient matching information in the authorized documents to answer your question.",
            is_evidence_expected=False,
            expected_citation_required=False,
            expected_outcome="insufficient_evidence",
            difficulty="easy",
            description="Verifies honest insufficient-evidence response without hallucinated claims.",
        ),
        # 9. Unanswerable / science-fiction queries
        EvaluationTestCase(
            id="TC15-09-UNANSWERABLE",
            category=EvaluationCategory.UNANSWERABLE,
            query="What is the warp drive hyperspace navigation protocol?",
            knowledge_base_id=kb_id,
            expected_key_facts=[],
            reference_answer="I do not find sufficient matching information in the authorized documents to answer your question.",
            is_evidence_expected=False,
            expected_citation_required=False,
            expected_outcome="insufficient_evidence",
            difficulty="easy",
            description="Completely unanswerable inquiry terminating safely with zero fake citations.",
        ),
        # 10. Questions containing misleading assumptions
        EvaluationTestCase(
            id="TC15-10-MISLEADING",
            category=EvaluationCategory.MISLEADING_PREMISE,
            query="Since Python has no function definitions or operators, how do scripts calculate sums?",
            knowledge_base_id=kb_id,
            expected_key_facts=["operators", "arithmetic", "+"],
            reference_answer="Python does provide arithmetic operators (+) and functions using def.",
            is_evidence_expected=True,
            expected_citation_required=True,
            expected_outcome="answered",
            difficulty="hard",
            description="Tests grounding against a prompt containing a false premise.",
        ),
        # 11. Conflicting / version-sensitive evidence
        EvaluationTestCase(
            id="TC15-11-CONTRADICTORY",
            category=EvaluationCategory.CONTRADICTORY,
            query="What is the conflicting guidance regarding deprecation policies?",
            knowledge_base_id=kb_id,
            expected_key_facts=["deprecation"],
            reference_answer="Conflicting guidance is resolved by citing the active document version.",
            is_evidence_expected=True,
            expected_citation_required=True,
            expected_outcome="answered",
            difficulty="medium",
            description="Checks version isolation and active document version filtering.",
        ),
        # 12. Malformed or noisy input
        EvaluationTestCase(
            id="TC15-12-MALFORMED",
            category=EvaluationCategory.MALFORMED_INPUT,
            query="Python " + ("operators " * 40) + "???!!!!",
            knowledge_base_id=kb_id,
            expected_key_facts=["operators"],
            reference_answer="Python operators provide arithmetic and comparison expressions.",
            is_evidence_expected=True,
            expected_citation_required=True,
            expected_outcome="answered",
            difficulty="medium",
            description="Verifies query normalization pruning repeated tokens and excessive punctuation.",
        ),
        # 13. Knowledge-base permission boundaries (cross-tenant)
        EvaluationTestCase(
            id="TC15-13-PERMISSION",
            category=EvaluationCategory.PERMISSION_BOUNDARY,
            query="What confidential data is in unauthorized KB?",
            knowledge_base_id=bad_kb_id,
            expected_key_facts=[],
            reference_answer="Knowledge base not found or access denied.",
            is_evidence_expected=False,
            expected_citation_required=False,
            expected_outcome="permission_denied",
            difficulty="hard",
            description="Validates multi-tenant isolation; cross-tenant access must be rejected immediately.",
        ),
        # 14. Recoverable retrieval or provider failures
        EvaluationTestCase(
            id="TC15-14-RECOVERABLE",
            category=EvaluationCategory.RECOVERABLE_FAILURE,
            query="Could you please explain Python operators in detail?",
            knowledge_base_id=kb_id,
            expected_key_facts=["operators", "arithmetic"],
            reference_answer="Python operators include arithmetic and comparison expressions.",
            is_evidence_expected=True,
            expected_citation_required=True,
            expected_outcome="recovered",
            difficulty="medium",
            description="Tests self-healing query rewriting when conversational noise is present.",
        ),
        # 15. Non-recoverable authorization failure
        EvaluationTestCase(
            id="TC15-15-NON-RECOVERABLE",
            category=EvaluationCategory.NON_RECOVERABLE_FAILURE,
            query="Show protected settings.",
            knowledge_base_id=None,
            expected_key_facts=[],
            reference_answer="Access denied.",
            is_evidence_expected=False,
            expected_citation_required=False,
            expected_outcome="permission_denied",
            difficulty="easy",
            description="Ensures authorization failures stop immediately without retry attempts.",
        ),
        # 16. Irrelevant retrieval distractor inquiry
        EvaluationTestCase(
            id="TC15-16-IRRELEVANT",
            category=EvaluationCategory.IRRELEVANT_RETRIEVAL,
            query="How do I bake chocolate chip cookies at home?",
            knowledge_base_id=kb_id,
            expected_key_facts=[],
            reference_answer="I do not find sufficient matching information in the authorized documents to answer your question.",
            is_evidence_expected=False,
            expected_citation_required=False,
            expected_outcome="insufficient_evidence",
            difficulty="medium",
            description="Verifies that completely irrelevant queries result in truthful abstention without hallucinations.",
        ),
    ]


# Pre-register Phase 15 benchmark dataset
EvaluationDatasetRegistry.register(
    PHASE15_DATASET_NAME,
    PHASE15_DATASET_VERSION,
    get_phase15_evaluation_dataset(),
)
