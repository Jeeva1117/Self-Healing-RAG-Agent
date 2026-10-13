"""Comprehensive end-to-end verification script for Phase 6 grounded chat integration.

Tests against the live database with real user documents:
- Python Knowledge Base (Python_A_to_Z_Notes_With_Examples.pdf)
- Data base KB (phase4_test_document.pdf)
- Jeevas resume KB (Jeevanantham_resume.pdf)
"""

import asyncio
from pathlib import Path
import sys
import uuid
from uuid import UUID

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))

from app.core.exceptions import AppError
from app.infrastructure.database.models import Document, DocumentChunk, KnowledgeBase
from app.infrastructure.database.session import AsyncSessionLocal
from app.schemas.chat import ChatRequest
from app.services.chat.chat_service import ChatService


async def run_live_verifications():
    print("=" * 70)
    print("STARTING LIVE REAL-DOCUMENT END-TO-END VERIFICATION")
    print("=" * 70)

    async with AsyncSessionLocal() as session:
        service = ChatService(session)

        # 1. Identify real user and knowledge bases
        user_id = UUID("ae028c74-561d-4fae-84ec-c88718b9ca89")
        kb_python_id = UUID("69618669-729f-430a-a946-f56785fca534")  # Python notes
        kb_data_id = UUID("ab2cc7f2-3361-4307-95a1-7b520b66cf49")    # Data base
        kb_resume_id = UUID("17f01e80-75a6-408b-9967-4d0058a9d14c")  # Jeevas resume

        # Test Scenario 1: "What are operators in Python?" on Python KB
        print("\n[Scenario 1] Ask 'What are operators in Python?' on Python KB:")
        req1 = ChatRequest(
            knowledge_base_id=kb_python_id,
            prompt="What are operators in Python?",
            top_k=5,
        )
        res1 = await service.send_message(req1, user_id=user_id)
        print("  -> Is Insufficient Evidence:", res1.is_insufficient_evidence)
        print("  -> Verification Status:", res1.verification_status)
        print("  -> Citations count:", len(res1.citations))
        assert not res1.is_insufficient_evidence, "Scenario 1 failed: Expected answer to be found"
        assert len(res1.citations) > 0, "Scenario 1 failed: Expected citations"
        first_cit = res1.citations[0]
        print(f"  -> First Citation: Doc='{first_cit.title}', Section='{first_cit.section}', Page={first_cit.page}")
        assert "python" in first_cit.title.lower(), "Scenario 1 failed: Expected Python document"
        assert "4. operators" in res1.content.lower() or "arithmetic" in res1.content.lower(), (
            "Scenario 1 failed: Content did not discuss operators"
        )
        print("  -> Scenario 1 PASSED!")

        # Test Scenario 2: Answer exists in Python PDF (Functions in Python)
        print("\n[Scenario 2] Ask 'How do functions work in Python?' on Python KB:")
        req2 = ChatRequest(
            knowledge_base_id=kb_python_id,
            prompt="How do functions work in Python?",
            top_k=5,
        )
        res2 = await service.send_message(req2, user_id=user_id)
        print("  -> Is Insufficient Evidence:", res2.is_insufficient_evidence)
        print("  -> Citations count:", len(res2.citations))
        assert not res2.is_insufficient_evidence, "Scenario 2 failed: Expected answer to be found"
        assert any("function" in c.snippet.lower() for c in res2.citations), (
            "Scenario 2 failed: Expected function chunk"
        )
        print("  -> Scenario 2 PASSED!")

        # Test Scenario 3: Unanswered question on Python PDF
        print("\n[Scenario 3] Ask 'What is the enterprise refund policy?' on Python KB:")
        req3 = ChatRequest(
            knowledge_base_id=kb_python_id,
            prompt="What is the enterprise refund policy?",
            top_k=5,
        )
        res3 = await service.send_message(req3, user_id=user_id)
        print("  -> Content:", res3.content)
        print("  -> Is Insufficient Evidence:", res3.is_insufficient_evidence)
        print("  -> Citations count:", len(res3.citations))
        assert res3.is_insufficient_evidence, "Scenario 3 failed: Expected insufficient evidence"
        assert len(res3.citations) == 0, "Scenario 3 failed: Citations must be empty for insufficient evidence"
        assert "sufficient matching information" in res3.content.lower() or "insufficient" in res3.content.lower()
        print("  -> Scenario 3 PASSED!")

        # Test Scenario 4: Cross-KB isolation: Python question on Data Base KB
        print("\n[Scenario 4] Ask 'What are operators in Python?' on Data base KB:")
        req4 = ChatRequest(
            knowledge_base_id=kb_data_id,
            prompt="What are operators in Python?",
            top_k=5,
        )
        res4 = await service.send_message(req4, user_id=user_id)
        print("  -> Is Insufficient Evidence:", res4.is_insufficient_evidence)
        print("  -> Citations count:", len(res4.citations))
        # No Python document chunks can leak
        for c in res4.citations:
            assert "python" not in c.title.lower(), f"Scenario 4 failed: Leaked document {c.title}"
        print("  -> Scenario 4 PASSED!")

        # Test Scenario 5: Unauthorized KB access
        print("\n[Scenario 5] Access Python KB with unauthorized user ID:")
        unauthorized_user = uuid.uuid4()
        req5 = ChatRequest(
            knowledge_base_id=kb_python_id,
            prompt="What are operators in Python?",
        )
        try:
            await service.send_message(req5, user_id=unauthorized_user)
            print("  -> ERROR: Allowed unauthorized access!")
            sys.exit(1)
        except AppError as e:
            assert e.status_code == 404
            assert e.code == "KNOWLEDGE_BASE_NOT_FOUND"
            print(f"  -> Successfully rejected with 404: {e.message}")
            print("  -> Scenario 5 PASSED!")

        # Test Scenario 6: Empty KB
        print("\n[Scenario 6] Create temporary empty KB and test:")
        empty_kb = KnowledgeBase(
            owner_id=user_id,
            name="Temporary Empty KB",
            description="Empty test KB",
        )
        session.add(empty_kb)
        await session.commit()
        await session.refresh(empty_kb)

        try:
            req6 = ChatRequest(
                knowledge_base_id=empty_kb.id,
                prompt="What is this document about?",
            )
            res6 = await service.send_message(req6, user_id=user_id)
            print("  -> Is Insufficient Evidence:", res6.is_insufficient_evidence)
            print("  -> Citations count:", len(res6.citations))
            assert res6.is_insufficient_evidence
            assert len(res6.citations) == 0
            print("  -> Scenario 6 PASSED!")
        finally:
            await session.delete(empty_kb)
            await session.commit()

        # Test Scenario 7: Validate IDs match actual database records
        print("\n[Scenario 7] Validate chunk and document IDs match real database records:")
        for cit in res1.citations:
            chunk_rec = await session.get(DocumentChunk, cit.chunk_id)
            assert chunk_rec is not None, f"Chunk {cit.chunk_id} not found in database!"
            doc_rec = await session.get(Document, cit.document_id)
            assert doc_rec is not None, f"Document {cit.document_id} not found in database!"
            assert chunk_rec.document_id == doc_rec.id
            assert doc_rec.original_filename == cit.title
            print(f"  -> Verified Chunk {cit.chunk_id} belongs to Document {cit.document_id} ({doc_rec.original_filename})")
        print("  -> Scenario 7 PASSED!")

    print("\n" + "=" * 70)
    print("ALL 7 LIVE REAL-DOCUMENT SCENARIOS PASSED WITH ZERO ERRORS!")
    print("=" * 70)


if __name__ == "__main__":
    asyncio.run(run_live_verifications())
