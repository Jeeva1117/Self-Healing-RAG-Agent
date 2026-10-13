"""Unit tests for CitationValidator in Phase 6."""

import uuid

from app.schemas.retrieval import RetrievalResultItem
from app.services.chat.citation_validator import CitationValidator


def _create_mock_chunk(chunk_index: int, page_number: int, content: str) -> RetrievalResultItem:
    """Helper to instantiate mock RetrievalResultItem."""
    return RetrievalResultItem(
        chunk_id=uuid.uuid4(),
        document_id=uuid.uuid4(),
        document_version_id=uuid.uuid4(),
        document_name="test_doc.pdf",
        chunk_index=chunk_index,
        content=content,
        character_count=len(content),
        page_number=page_number,
        section_title=f"Section {chunk_index}",
        vector_score=0.85,
        keyword_score=0.75,
        hybrid_score=0.80,
        reranker_score=0.90,
        final_rank=chunk_index,
        stage_provenance="hybrid",
    )


def test_citation_validator_single_and_multi():
    """Verify valid single and multiple bracketed citations."""
    chunk1 = _create_mock_chunk(1, 1, "Arithmetic operators include +, -, *.")
    chunk2 = _create_mock_chunk(2, 2, "Comparison operators include ==, !=, >.")
    retrieved = [chunk1, chunk2]

    raw_answer = (
        "Python supports arithmetic operators like addition [1]. "
        "It also supports comparison operators [2]. "
        "Both operator categories form expressions [1, 2]."
    )

    result = CitationValidator.validate_and_map(raw_answer, retrieved)

    assert result.validation_passed is True
    assert result.used_source_count == 2
    assert len(result.sources) == 2
    assert result.sources[0].is_cited is True
    assert result.sources[1].is_cited is True

    # Check active citations
    assert len(result.active_citations) == 2
    assert result.active_citations[0].chunk_id == chunk1.chunk_id
    assert result.active_citations[1].chunk_id == chunk2.chunk_id

    # Check claims extraction
    assert len(result.claim_citations) >= 3
    # Claim 1 should cite chunk 1
    assert result.claim_citations[0].source_chunk_ids == [chunk1.chunk_id]
    assert "[1]" not in result.claim_citations[0].text
    # Claim 3 should cite both chunk 1 and chunk 2
    assert set(result.claim_citations[2].source_chunk_ids) == {chunk1.chunk_id, chunk2.chunk_id}


def test_citation_validator_removes_hallucinated_citations():
    """Verify that hallucinated citations such as [99] are removed and flagged."""
    chunk1 = _create_mock_chunk(1, 1, "Python variables are dynamically typed.")
    retrieved = [chunk1]

    raw_answer = "Python variables are dynamic [1], but memory is managed by aliens [99]."
    result = CitationValidator.validate_and_map(raw_answer, retrieved)

    # [99] must be removed from the sanitized answer
    assert "[99]" not in result.sanitized_answer
    assert "[1]" in result.sanitized_answer
    # Flag validation_passed as False because model produced hallucinated citation
    assert result.validation_passed is False
    assert result.used_source_count == 1
    assert result.sources[0].is_cited is True


def test_citation_validator_mixed_brackets():
    """Verify mixed brackets with valid and invalid IDs: [1, 50]."""
    chunk1 = _create_mock_chunk(1, 1, "Python is interpreted.")
    retrieved = [chunk1]

    raw_answer = "Python executes bytecode on the virtual machine [1, 50]."
    result = CitationValidator.validate_and_map(raw_answer, retrieved)

    assert result.sanitized_answer == "Python executes bytecode on the virtual machine [1]."
    assert result.validation_passed is False  # Because 50 was out of bounds
    assert result.used_source_count == 1


def test_citation_validator_no_citations_fallback():
    """Verify fallback behavior when answer contains no bracketed citations."""
    chunk1 = _create_mock_chunk(1, 1, "Python list indexing starts at 0.")
    retrieved = [chunk1]

    raw_answer = "List indexing begins with 0 in Python."
    result = CitationValidator.validate_and_map(raw_answer, retrieved)

    assert result.sanitized_answer == raw_answer
    assert result.used_source_count == 0
    assert result.sources[0].is_cited is False
    # Active citations falls back to retrieved candidates for auditability
    assert len(result.active_citations) == 1
    assert result.active_citations[0].chunk_id == chunk1.chunk_id
    assert len(result.claim_citations) == 0


def test_citation_validator_empty_retrieved_chunks():
    """Verify behavior when no chunks were retrieved."""
    result = CitationValidator.validate_and_map(
        "I could not find sufficient matching information in the selected knowledge base.",
        [],
    )

    assert result.validation_passed is True
    assert result.used_source_count == 0
    assert len(result.sources) == 0
    assert len(result.active_citations) == 0
    assert len(result.claim_citations) == 0
