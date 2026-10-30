"""Regression and audit tests for citation relevance, topic-aware chunking, and ranking."""

import uuid

import pytest
from app.domain.interfaces.llm import LLMMessage
from app.infrastructure.llm.grounded_synthesis_provider import (
    INSUFFICIENT_EVIDENCE_MESSAGE,
    GroundedSynthesisProvider,
)
from app.infrastructure.rerank.flashrank_reranker import FlashRankReranker
from app.schemas.retrieval import RetrievalResultItem
from app.services.chat.citation_validator import CitationValidator
from app.services.chunker import DocumentChunker
from app.services.parsers.base import ParsedDocument, ParsedUnit

PAGE_3_RAW_TEXT = """Python A to Z Notes — Beginner to Intermediate
Page 3
Type conversion
 number_text = "42"
number = int(number_text)
decimal = float("3.14")
text = str(100)
print(number + 8)   # 50
Conversion can fail if the text is not a valid representation, for example int('hello').
3. Input and Output
 name = input("Enter your name: ")
age = int(input("Enter your age: "))
print("Hello", name)
print(f"Next year you will be {age + 1}.")
input() returns text (str), so convert it with int() or float() when you need a number.
f-strings
 product = "book"
price = 250
print(f"The {product} costs Rs. {price}.")
4. Operators
Arithmetic
 a, b = 10, 3
print(a + b)   # 13
print(a - b)   # 7
print(a * b)   # 30
print(a / b)   # 3.333...
print(a // b)  # 3: floor division
print(a % b)   # 1: remainder
print(a ** b)  # 1000: power
Comparison and logical operators
 x = 7
print(x > 5)                 # True
print(x == 7)                # True
print(x != 2)                # True
print(x > 3 and x < 10)      # True
print(x < 3 or x == 7)       # True
print(not (x == 7))          # False
Assignment and membership
 score = 5
score += 2       # score becomes 7
print("py" in "python")      # True
print(4 not in [1, 2, 3])    # True
5. Conditional Statements
 marks = 78
if marks >= 90:
    grade = "A"
elif marks >= 75:
    grade = "B"
elif marks >= 50:
    grade = "C"
else:
    grade = "Needs improvement"
print(grade)  # B"""


PAGE_6_FUNCTIONS_TEXT = """Python A to Z Notes — Beginner to Intermediate
Page 6
13. Functions
 def add(a, b):
    return a + b
answer = add(4, 6)
print(answer)  # 10
Parameters, default arguments, and return values
 def greet(name, title="Student"):
    return f"Hello, {title} {name}!"
print(greet("Jeeva"))
print(greet("Anita", title="Dr."))
Variable arguments
 def total_sum(*numbers):
    return sum(numbers)
print(total_sum(1, 2, 3, 4))  # 10
14. Scope and Lambda
 rate = 2  # global scope
def calculate(amount):
    bonus = 5  # local scope
    return amount * rate + bonus
print(calculate(10))  # 25
Lambda is a small anonymous function:
 square = lambda x: x * x
print(square(6))  # 36
Use normal functions with def for anything beyond a trivial one-line expression."""


PAGE_12_ROADMAP_TEXT = """Python A to Z Notes — Beginner to Intermediate
Page 12
6. What is the difference between shallow copy and deep copy?
7. Write a custom exception NegativeBalanceError.
8. How does binary search achieve O(log n) time?
9. Explain how sets achieve O(1) average lookup.
10. What is the difference between *args and **kwargs?
11. Write a generator to produce Fibonacci numbers lazily.
12. Why should you avoid mutable default arguments in functions?
13. How does pandas handle missing values?
14. What is overfitting, and how do you reduce it?
15. Explain the difference between supervised and unsupervised learning.
32. Answer Key / Hints
33. Suggested Learning Roadmap
 Stage
Topics
Practice goal
1. Basics
Variables, types, input/output, operators
Write 10 tiny programs
2. Control flow
if/elif/else, for, while
Number and pattern problems
3. Collections
Strings, lists, tuples, sets, dictionaries
20 easy coding problems
4. Functions
Parameters, return, scope, comprehensions
Break repeated code into functions
5. Intermediate
Files, exceptions, modules, OOP, generators
Build a small CLI project
6. DSA
Complexity, arrays, strings, hashing, two pointers, binary search
Solve consistently and review mistakes
7. Data/AI
NumPy, pandas, scikit-learn, APIs, ML fundamentals
Build a small data project"""


def test_chunker_separates_python_page_3_topics():
    """Verify that multi-topic Page 3 is split into dedicated, unmerged topic chunks."""
    chunker = DocumentChunker(chunk_size=500, chunk_overlap=50)
    parsed_unit = ParsedUnit(
        text=PAGE_3_RAW_TEXT,
        page_number=3,
        section_title="Page 3",
        unit_index=3,
    )
    parsed_doc = ParsedDocument(units=[parsed_unit])

    chunks = chunker.chunk_document(
        parsed_doc=parsed_doc,
        document_id="doc-test-1",
        document_version_id="ver-test-1",
        source_filename="Python_A_to_Z_Notes_With_Examples.pdf",
    )

    # Must produce separate chunks for Type conversion, Input & Output, Operators, Conditional Statements
    assert len(chunks) == 4, f"Expected 4 chunks, got {len(chunks)}"

    chunk_titles = [c.section_title for c in chunks]
    assert "Type conversion" in chunk_titles
    assert "3. Input and Output" in chunk_titles
    assert "4. Operators" in chunk_titles
    assert "5. Conditional Statements" in chunk_titles

    # Verify all chunks retain the authentic page number 3
    for c in chunks:
        assert c.page_number == 3
        assert c.character_count > 0
        assert c.token_count > 0
        assert c.end_offset > c.start_offset

    # Find the operators chunk specifically
    op_chunk = next(c for c in chunks if c.section_title == "4. Operators")

    # 1. Operators chunk MUST contain arithmetic, comparison, logical, assignment, membership operators
    assert "Arithmetic" in op_chunk.content
    assert "Comparison and logical operators" in op_chunk.content
    assert "Assignment and membership" in op_chunk.content
    assert "a, b = 10, 3" in op_chunk.content
    assert 'in "python"' in op_chunk.content

    # 2. Operators chunk MUST NOT contain unrelated topics
    assert "Type conversion" not in op_chunk.content
    assert "number_text" not in op_chunk.content
    assert "3. Input and Output" not in op_chunk.content
    assert "f-strings" not in op_chunk.content
    assert "5. Conditional Statements" not in op_chunk.content
    assert 'grade = "A"' not in op_chunk.content


def test_chunker_separates_python_page_6_functions():
    """Verify that Page 6 separates 13. Functions and 14. Scope and Lambda."""
    chunker = DocumentChunker(chunk_size=500, chunk_overlap=50)
    parsed_unit = ParsedUnit(
        text=PAGE_6_FUNCTIONS_TEXT,
        page_number=6,
        section_title="Page 6",
        unit_index=6,
    )
    parsed_doc = ParsedDocument(units=[parsed_unit])

    chunks = chunker.chunk_document(
        parsed_doc=parsed_doc,
        document_id="doc-test-1",
        document_version_id="ver-test-1",
        source_filename="Python_A_to_Z_Notes_With_Examples.pdf",
    )

    assert len(chunks) == 2, f"Expected 2 chunks, got {len(chunks)}"
    assert chunks[0].section_title == "13. Functions"
    assert chunks[0].page_number == 6
    assert "def add(a, b):" in chunks[0].content
    assert "14. Scope and Lambda" not in chunks[0].content

    assert chunks[1].section_title == "14. Scope and Lambda"
    assert chunks[1].page_number == 6
    assert "lambda x: x * x" in chunks[1].content


@pytest.mark.asyncio
async def test_reranker_relevance_for_operator_queries():
    """Regression test: 'What are operators in Python?' ranks 4. Operators highest with significant score."""
    reranker = FlashRankReranker()
    query = "What are operators in Python?"

    op_content = (
        "4. Operators\n"
        "Arithmetic\n"
        " a, b = 10, 3\n"
        "print(a + b)   # 13\n"
        "Comparison and logical operators\n"
        " x = 7\n"
        "print(x > 5 and x < 10) # True\n"
        "Assignment and membership\n"
        "print('py' in 'python') # True"
    )

    cond_content = "5. Conditional Statements\n marks = 78\nif marks >= 90:\n    grade = 'A'\nelse:\n    grade = 'B'"

    type_content = "Type conversion\n number_text = '42'\nnumber = int(number_text)\nprint(number + 8)"

    docs = [
        {
            "id": "operators-chunk",
            "content": f"Document: Python A to Z Notes With Examples | Section: 4. Operators\n{op_content}",
            "metadata": {"page_number": 3, "section_title": "4. Operators"},
            "original_rank": 1,
        },
        {
            "id": "conditionals-chunk",
            "content": f"Document: Python A to Z Notes With Examples | Section: 5. Conditional Statements\n{cond_content}",
            "metadata": {"page_number": 3, "section_title": "5. Conditional Statements"},
            "original_rank": 2,
        },
        {
            "id": "types-chunk",
            "content": f"Document: Python A to Z Notes With Examples | Section: Type conversion\n{type_content}",
            "metadata": {"page_number": 3, "section_title": "Type conversion"},
            "original_rank": 3,
        },
    ]

    ranked = await reranker.rerank(query=query, documents=docs, top_k=3)

    assert len(ranked) == 3
    # Operators chunk must be ranked #1
    assert ranked[0].document_id == "operators-chunk"
    # Score for operators must be dominant (e.g. > 0.20), far above conditionals and types
    assert ranked[0].relevance_score > 0.20, f"Expected high score, got {ranked[0].relevance_score}"
    assert ranked[0].relevance_score > ranked[1].relevance_score * 5
    assert ranked[0].relevance_score > ranked[2].relevance_score * 5


@pytest.mark.asyncio
async def test_reranker_relevance_for_function_queries():
    """Regression test: 'What are functions in Python?' ranks 13. Functions highest."""
    reranker = FlashRankReranker()
    query = "What are functions in Python?"

    func_content = (
        "13. Functions\n"
        " def add(a, b):\n"
        "    return a + b\n"
        "answer = add(4, 6)\n"
        "print(answer)  # 10\n"
        "Parameters, default arguments, and return values"
    )

    op_content = "4. Operators\nArithmetic\n a, b = 10, 3\nprint(a + b)"

    docs = [
        {
            "id": "functions-chunk",
            "content": f"Document: Python A to Z Notes With Examples | Section: 13. Functions\n{func_content}",
            "metadata": {"page_number": 6, "section_title": "13. Functions"},
            "original_rank": 1,
        },
        {
            "id": "operators-chunk",
            "content": f"Document: Python A to Z Notes With Examples | Section: 4. Operators\n{op_content}",
            "metadata": {"page_number": 3, "section_title": "4. Operators"},
            "original_rank": 2,
        },
    ]

    ranked = await reranker.rerank(query=query, documents=docs, top_k=2)

    assert ranked[0].document_id == "functions-chunk"
    assert ranked[0].relevance_score > 0.30
    assert ranked[0].relevance_score > ranked[1].relevance_score * 10


@pytest.mark.asyncio
async def test_reranker_relevance_for_unrelated_queries():
    """Regression test: Unrelated questions produce very low relevance scores (< 0.05)."""
    reranker = FlashRankReranker()
    query = "Explain quantum entanglement in interstellar deep space wormholes"

    op_content = "4. Operators\nArithmetic\n a, b = 10, 3\nprint(a + b)"

    docs = [
        {
            "id": "operators-chunk",
            "content": f"Document: Python A to Z Notes With Examples | Section: 4. Operators\n{op_content}",
            "metadata": {"page_number": 3, "section_title": "4. Operators"},
            "original_rank": 1,
        },
    ]

    ranked = await reranker.rerank(query=query, documents=docs, top_k=1)

    assert len(ranked) == 1
    # Score for completely unrelated query against python operators must be tiny (< 0.05)
    assert ranked[0].relevance_score < 0.05, f"Expected < 0.05, got {ranked[0].relevance_score}"


def test_citation_validator_preserves_authentic_metadata():
    """Verify CitationValidator never fabricates page numbers, scores, or citation provenance."""
    chunk_id = uuid.uuid4()
    doc_id = uuid.uuid4()

    chunk = RetrievalResultItem(
        chunk_id=chunk_id,
        document_id=doc_id,
        document_name="Python_A_to_Z_Notes_With_Examples.pdf",
        chunk_index=9,
        content="4. Operators\nArithmetic\n a, b = 10, 3\nprint(a + b) # 13",
        character_count=55,
        page_number=3,
        section_title="4. Operators",
        vector_score=0.8993,
        reranker_score=0.3971,
        final_rank=1,
        stage_provenance="hybrid",
    )

    raw_answer = "Python provides arithmetic operators such as addition [1]."
    result = CitationValidator.validate_and_map(raw_answer, [chunk])

    assert result.validation_passed is True
    assert len(result.active_citations) == 1
    citation = result.active_citations[0]

    # Verify authentic provenance fields are preserved exactly without fabrication
    assert citation.chunk_id == chunk_id
    assert citation.document_id == doc_id
    assert citation.page == 3
    assert citation.section == "4. Operators"
    assert citation.title == "Python_A_to_Z_Notes_With_Examples.pdf"
    assert citation.snippet == chunk.content
    assert citation.relevance_score == 0.3971


def test_chunker_keeps_learning_roadmap_intact():
    """Verify that Page 12's Suggested Learning Roadmap is kept in a coherent single chunk."""
    chunker = DocumentChunker(chunk_size=1000, chunk_overlap=100)
    parsed_unit = ParsedUnit(
        text=PAGE_12_ROADMAP_TEXT,
        page_number=12,
        section_title="Page 12",
        unit_index=12,
    )
    parsed_doc = ParsedDocument(units=[parsed_unit])
    chunks = chunker.chunk_document(parsed_doc, document_id=uuid.uuid4())

    roadmap_chunks = [c for c in chunks if "33. Suggested Learning Roadmap" in c.section_title]
    assert len(roadmap_chunks) == 1, f"Expected 1 roadmap chunk, found {len(roadmap_chunks)}"
    roadmap_chunk = roadmap_chunks[0]

    # Verify that all 7 roadmap stages are contained within this single chunk
    assert "1. Basics" in roadmap_chunk.content
    assert "2. Control flow" in roadmap_chunk.content
    assert "3. Collections" in roadmap_chunk.content
    assert "4. Functions" in roadmap_chunk.content
    assert "5. Intermediate" in roadmap_chunk.content
    assert "6. DSA" in roadmap_chunk.content
    assert "7. Data/AI" in roadmap_chunk.content
    assert roadmap_chunk.page_number == 12


@pytest.mark.asyncio
async def test_grounded_synthesis_topic_list_extracts_actual_topics():
    """Verify that topic list queries extract actual PDF topics and avoid generic headings."""
    provider = GroundedSynthesisProvider()
    query = "What are the core concepts covered in this knowledge base? List the main topics from the uploaded Python notes."

    evidence_context = (
        "=== UNTRUSTED AUTHORIZED REFERENCE MATERIAL ===\n"
        "[Evidence 1] (Document: Python_A_to_Z_Notes_With_Examples.pdf, Page: 12, Section: 33. Suggested Learning Roadmap)\n"
        "33. Suggested Learning Roadmap\n"
        " Stage\nTopics\nPractice goal\n"
        "1. Basics\nVariables, types, input/output, operators\nWrite 10 tiny programs\n"
        "2. Control flow\nif/elif/else, for, while\nNumber and pattern problems\n"
        "3. Collections\nStrings, lists, tuples, sets, dictionaries\n20 easy coding problems\n"
        "4. Functions\nParameters, return, scope, comprehensions\nBreak repeated code into functions\n"
        "5. Intermediate\nFiles, exceptions, modules, OOP, generators\nBuild a small CLI project\n"
        "6. DSA\nComplexity, arrays, strings, hashing, two pointers, binary search\nSolve consistently and review mistakes\n"
        "7. Data/AI\nNumPy, pandas, scikit-learn, APIs, ML fundamentals\nBuild a small data project\n\n"
        "[Evidence 2] (Document: Python_A_to_Z_Notes_With_Examples.pdf, Page: 1, Section: PYTHON A TO Z)\n"
        "PYTHON A TO Z\n Complete Beginner-to-Intermediate Notes\n"
        " Concepts Syntax Examples Common Mistakes Practice Questions\nStart here\n\n"
        "[Evidence 3] (Document: Python_A_to_Z_Notes_With_Examples.pdf, Page: 2, Section: 2. Core Data Types)\n"
        "2. Core Data Types\nCommon built-in types include int, float, str, bool, NoneType.\n"
        "=== END OF REFERENCE MATERIAL ==="
    )

    messages = [
        LLMMessage(role="system", content=evidence_context),
        LLMMessage(role="user", content=query),
    ]

    resp = await provider.generate(messages=messages)
    answer = resp.content

    # 1. Must extract verified topic names from roadmap
    assert "Basics" in answer
    assert "Control flow" in answer
    assert "Collections" in answer
    assert "Functions" in answer
    assert "Intermediate" in answer
    assert "DSA" in answer
    assert "Data/AI" in answer

    # 2. Must NOT invent generic column headings as the topic list
    assert "Concepts Syntax Examples Common Mistakes Practice Questions" not in answer

    # 3. Must link citation to evidence 1 (Page 12)
    assert "[1]" in answer
    assert "Page 12" in answer


@pytest.mark.asyncio
async def test_grounded_synthesis_operator_query():
    """Verify that operator query answers using 4. Operators evidence with authentic citation."""
    provider = GroundedSynthesisProvider()
    query = "What are operators in Python?"

    evidence_context = (
        "=== UNTRUSTED AUTHORIZED REFERENCE MATERIAL ===\n"
        "[Evidence 1] (Document: Python_A_to_Z_Notes_With_Examples.pdf, Page: 3, Section: 4. Operators)\n"
        "4. Operators\nArithmetic\n a, b = 10, 3\nprint(a + b)   # 13\n"
        "print(a - b)   # 7\nprint(a * b)   # 30\nprint(a / b)   # 3.333...\n"
        "Comparison and logical operators\n x = 7\nprint(x > 5)  # True\n"
        "=== END OF REFERENCE MATERIAL ==="
    )

    messages = [
        LLMMessage(role="system", content=evidence_context),
        LLMMessage(role="user", content=query),
    ]

    resp = await provider.generate(messages=messages)
    answer = resp.content

    assert "Arithmetic" in answer or "print(a + b)" in answer
    assert "[1]" in answer
    assert "Page 3" in answer


@pytest.mark.asyncio
async def test_grounded_synthesis_functions_query():
    """Verify that functions query answers using 13. Functions evidence with authentic citation."""
    provider = GroundedSynthesisProvider()
    query = "How do functions work in Python?"

    evidence_context = (
        "=== UNTRUSTED AUTHORIZED REFERENCE MATERIAL ===\n"
        "[Evidence 1] (Document: Python_A_to_Z_Notes_With_Examples.pdf, Page: 6, Section: 13. Functions)\n"
        "13. Functions\n def add(a, b):\n    return a + b\nanswer = add(4, 6)\n"
        "print(answer)  # 10\nParameters, default arguments, and return values\n"
        "=== END OF REFERENCE MATERIAL ==="
    )

    messages = [
        LLMMessage(role="system", content=evidence_context),
        LLMMessage(role="user", content=query),
    ]

    resp = await provider.generate(messages=messages)
    answer = resp.content

    assert "def add(a, b)" in answer or "return a + b" in answer
    assert "[1]" in answer
    assert "Page 6" in answer


@pytest.mark.asyncio
async def test_grounded_synthesis_insufficient_evidence_unrelated_query():
    """Verify that completely unrelated queries honestly return insufficient evidence."""
    provider = GroundedSynthesisProvider()
    query = "What is the quantum chromodynamics quark-gluon plasma temperature?"

    evidence_context = (
        "=== UNTRUSTED AUTHORIZED REFERENCE MATERIAL ===\n"
        "[Evidence 1] (Document: Python_A_to_Z_Notes_With_Examples.pdf, Page: 3, Section: 4. Operators)\n"
        "4. Operators\nArithmetic\n a, b = 10, 3\nprint(a + b)\n"
        "=== END OF REFERENCE MATERIAL ==="
    )

    messages = [
        LLMMessage(role="system", content=evidence_context),
        LLMMessage(role="user", content=query),
    ]

    resp = await provider.generate(messages=messages)
    assert resp.content == INSUFFICIENT_EVIDENCE_MESSAGE


@pytest.mark.asyncio
async def test_reranker_prioritizes_learning_roadmap_for_core_concepts_query():
    """Verify neural reranker ranks roadmap chunk top-1 for core concepts / topics query."""
    reranker = FlashRankReranker()
    query = "What are the core concepts covered in this knowledge base? List the main topics from the uploaded Python notes."

    roadmap_content = (
        "33. Suggested Learning Roadmap\n"
        "Stage Topics Practice goal\n"
        "1. Basics Variables, types, input/output, operators\n"
        "2. Control flow if/elif/else, for, while\n"
        "3. Collections Strings, lists, tuples, sets, dictionaries\n"
        "4. Functions Parameters, return, scope, comprehensions\n"
        "5. Intermediate Files, exceptions, modules, OOP, generators\n"
        "6. DSA Complexity, arrays, strings, hashing\n"
        "7. Data/AI NumPy, pandas, scikit-learn"
    )

    page1_content = (
        "PYTHON A TO Z\n"
        "Complete Beginner-to-Intermediate Notes\n"
        "Concepts Syntax Examples Common Mistakes Practice Questions"
    )

    docs = [
        {
            "id": "page-1-chunk",
            "content": f"Document: Python A to Z Notes With Examples | Section: PYTHON A TO Z\n{page1_content}",
            "metadata": {"page_number": 1, "section_title": "PYTHON A TO Z"},
            "original_rank": 1,
        },
        {
            "id": "roadmap-chunk",
            "content": f"Document: Python A to Z Notes With Examples | Section: 33. Suggested Learning Roadmap\n{roadmap_content}",
            "metadata": {"page_number": 12, "section_title": "33. Suggested Learning Roadmap"},
            "original_rank": 2,
        },
    ]

    ranked = await reranker.rerank(query=query, documents=docs, top_k=2)

    assert ranked[0].document_id == "roadmap-chunk"
    assert ranked[0].relevance_score > 0.10
    assert ranked[0].relevance_score > ranked[1].relevance_score * 2
