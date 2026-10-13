"""Live End-to-End Integration and Pipeline Verification Script.
Executes against the running FastAPI server on http://127.0.0.1:8000
and local PostgreSQL database.
"""

import asyncio
import io
import time
import sys
import uuid
import httpx
from sqlalchemy import text
from app.infrastructure.database.session import AsyncSessionLocal
async_session = AsyncSessionLocal
BASE_URL = "http://127.0.0.1:8000"
API_BASE = f"{BASE_URL}/api/v1"

results = {
    "total": 0,
    "passed": 0,
    "failed": 0,
    "details": []
}

def record_result(category: str, name: str, passed: bool, duration_ms: float, details: str = ""):
    results["total"] += 1
    if passed:
        results["passed"] += 1
        status = "PASS"
    else:
        results["failed"] += 1
        status = "FAIL"
    entry = {
        "category": category,
        "name": name,
        "status": status,
        "duration_ms": round(duration_ms, 2),
        "details": details
    }
    results["details"].append(entry)
    print(f"[{status}] {category} -> {name} ({round(duration_ms, 2)}ms) {details}")

async def run_live_tests():
    print("=" * 70)
    print("STARTING FULL LIVE END-TO-END VIRTUAL TESTING")
    print(f"Target API: {BASE_URL}")
    print(f"Target DB:  Local PostgreSQL")
    print("=" * 70)

    async with httpx.AsyncClient(timeout=60.0) as client:
        # -------------------------------------------------------------
        # Startup & Health Endpoints
        # -------------------------------------------------------------
        t0 = time.perf_counter()
        r = await client.get(f"{API_BASE}/health")
        dt = (time.perf_counter() - t0) * 1000
        health_data = r.json() if r.status_code == 200 else {}
        record_result(
            "Startup & Health",
            "Health Endpoint Probe",
            r.status_code == 200 and health_data.get("status") in ("ok", "healthy"),
            dt,
            f"status={r.status_code}, body={health_data}"
        )

        # -------------------------------------------------------------
        # Authentication & Authorization E2E
        # -------------------------------------------------------------
        # Unauthenticated request rejection
        t0 = time.perf_counter()
        r = await client.get(f"{API_BASE}/auth/me")
        dt = (time.perf_counter() - t0) * 1000
        record_result(
            "Authentication",
            "Unauthenticated Request Rejection",
            r.status_code == 401,
            dt,
            f"status={r.status_code}"
        )

        # Demo login
        t0 = time.perf_counter()
        r = await client.post(f"{API_BASE}/auth/demo-login")
        dt = (time.perf_counter() - t0) * 1000
        login_data = r.json().get("data", {}) if r.status_code == 200 else {}
        access_token = login_data.get("access_token")
        user_info = login_data.get("user", {})
        user_id = user_info.get("id")
        record_result(
            "Authentication",
            "Demo Login Flow",
            r.status_code == 200 and bool(access_token),
            dt,
            f"user_id={user_id}, email={user_info.get('email')}"
        )

        auth_headers = {"Authorization": f"Bearer {access_token}"}

        # Profile validation
        t0 = time.perf_counter()
        r = await client.get(f"{API_BASE}/auth/me", headers=auth_headers)
        dt = (time.perf_counter() - t0) * 1000
        record_result(
            "Authentication",
            "Authenticated Profile Fetch (/auth/me)",
            r.status_code == 200 and r.json().get("data", {}).get("email") == "demo@selfhealingrag.local",
            dt,
            f"status={r.status_code}"
        )

        # Tampered JWT rejection
        t0 = time.perf_counter()
        r = await client.get(f"{API_BASE}/auth/me", headers={"Authorization": "Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.tampered.token"})
        dt = (time.perf_counter() - t0) * 1000
        record_result(
            "Authentication",
            "Tampered Token Rejection",
            r.status_code == 401,
            dt,
            f"status={r.status_code}"
        )

        # -------------------------------------------------------------
        # Document Upload & Ingestion E2E
        # -------------------------------------------------------------
        # Create Test Knowledge Base
        test_kb_name = f"E2E_Test_KB_{uuid.uuid4().hex[:6]}"
        t0 = time.perf_counter()
        r = await client.post(
            f"{API_BASE}/knowledge-bases",
            json={"name": test_kb_name, "description": "Temporary isolated KB for virtual QA automation"},
            headers=auth_headers
        )
        dt = (time.perf_counter() - t0) * 1000
        kb_id = r.json().get("data", {}).get("id")
        record_result(
            "Ingestion",
            "Create Dedicated Test Knowledge Base",
            r.status_code == 201 and bool(kb_id),
            dt,
            f"kb_id={kb_id}, name={test_kb_name}"
        )

        # Unsupported file upload rejection
        t0 = time.perf_counter()
        bad_files = {"file": ("malicious.exe", io.BytesIO(b"MZ\x90\x00\x03\x00\x00\x00"), "application/x-dosexec")}
        r = await client.post(f"{API_BASE}/knowledge-bases/{kb_id}/documents", files=bad_files, headers=auth_headers)
        dt = (time.perf_counter() - t0) * 1000
        record_result(
            "Ingestion",
            "Unsupported Executable File Rejection",
            r.status_code in (400, 415, 422),
            dt,
            f"status={r.status_code}"
        )

        # Valid synthetic document upload
        synthetic_fact = (
            "PROJECT QUANTUM_LEAP SUMMARY:\n"
            "Initiated in September 2028 under the leadership of Dr. Elena Rostova at Zurich Quantum Laboratories. "
            "The primary objective is the deployment of repeater-less quantum key distribution over 850km of standard single-mode optical fiber. "
            "The core technological breakthrough is the cryogenic photon stabilizer known as CPS-9, operating at 1.4 Kelvin. "
            "Total phase-one grant funding allocated for Project QuantumLeap was 14.8 million Swiss Francs."
        )
        t0 = time.perf_counter()
        good_files = {"file": ("quantum_leap_whitepaper.txt", io.BytesIO(synthetic_fact.encode("utf-8")), "text/plain")}
        r = await client.post(f"{API_BASE}/knowledge-bases/{kb_id}/documents", files=good_files, headers=auth_headers)
        dt = (time.perf_counter() - t0) * 1000
        doc_id = r.json().get("data", {}).get("id")
        record_result(
            "Ingestion",
            "Upload Valid Synthetic Document",
            r.status_code in (200, 201, 202) and bool(doc_id),
            dt,
            f"doc_id={doc_id}"
        )

        # Wait and poll for ingestion to complete (READY status)
        t0 = time.perf_counter()
        status = "PENDING"
        for _ in range(15):
            await asyncio.sleep(1.0)
            r = await client.get(f"{API_BASE}/documents/{doc_id}", headers=auth_headers)
            if r.status_code == 200:
                status = r.json().get("data", {}).get("status")
                if status in ("READY", "FAILED"):
                    break
        dt = (time.perf_counter() - t0) * 1000
        record_result(
            "Ingestion",
            "Document Ingestion Pipeline Completion",
            status == "READY",
            dt,
            f"final_status={status}"
        )

        # Database inspection: verify chunks and embeddings stored
        t0 = time.perf_counter()
        async with async_session() as db:
            result = await db.execute(
                text("SELECT count(*), avg(character_count) FROM document_chunks WHERE document_id = :doc_id"),
                {"doc_id": doc_id}
            )
            row = result.fetchone()
            chunk_count = row[0] if row else 0
            avg_chars = row[1] if row else 0

            # Check vector embeddings dimension via ORM model
            from app.infrastructure.database.models import DocumentChunk
            from sqlalchemy import select
            chunk_stmt = select(DocumentChunk).where(DocumentChunk.document_id == uuid.UUID(doc_id)).limit(1)
            chunk_obj = (await db.execute(chunk_stmt)).scalar_one_or_none()
            has_embedding = chunk_obj is not None and chunk_obj.embedding is not None
            vec_dims = len(chunk_obj.embedding) if (chunk_obj and chunk_obj.embedding) else 0
        dt = (time.perf_counter() - t0) * 1000
        record_result(
            "Database & Storage",
            "Verify Stored Chunks & FastEmbed Vectors",
            chunk_count > 0 and has_embedding and vec_dims == 384,
            dt,
            f"chunks={chunk_count}, avg_chars={round(avg_chars or 0, 1)}, dims={vec_dims}"
        )

        # -------------------------------------------------------------
        # Retrieval Tests
        # -------------------------------------------------------------
        # Semantic retrieval on exact question
        t0 = time.perf_counter()
        r = await client.post(
            f"{API_BASE}/retrieval/search",
            json={
                "knowledge_base_id": kb_id,
                "query": "Who leads Project Quantum Leap and where is it located?",
                "top_k": 3,
                "mode": "hybrid"
            },
            headers=auth_headers
        )
        dt = (time.perf_counter() - t0) * 1000
        retrieval_data = r.json().get("data", {}).get("results", []) if r.status_code == 200 else []
        top_content = retrieval_data[0].get("content", "") if retrieval_data else ""
        record_result(
            "RAG Retrieval",
            "Hybrid Retrieval (Exact/Semantic Match)",
            len(retrieval_data) > 0 and "Elena Rostova" in top_content,
            dt,
            f"results_returned={len(retrieval_data)}, top_match_found={'Elena Rostova' in top_content}"
        )

        # Paraphrased keyword search
        t0 = time.perf_counter()
        r = await client.post(
            f"{API_BASE}/retrieval/search",
            json={
                "knowledge_base_id": kb_id,
                "query": "cryogenic photon stabilizer CPS-9 operating temperature",
                "top_k": 3,
                "mode": "hybrid"
            },
            headers=auth_headers
        )
        dt = (time.perf_counter() - t0) * 1000
        retrieval_data = r.json().get("data", {}).get("results", []) if r.status_code == 200 else []
        top_content = retrieval_data[0].get("content", "") if retrieval_data else ""
        record_result(
            "RAG Retrieval",
            "Hybrid Retrieval (Keyword / Paraphrased)",
            len(retrieval_data) > 0 and "1.4 Kelvin" in top_content,
            dt,
            f"results_returned={len(retrieval_data)}, matched_cps9={'1.4 Kelvin' in top_content}"
        )

        # Irrelevant query
        t0 = time.perf_counter()
        r = await client.post(
            f"{API_BASE}/retrieval/search",
            json={
                "knowledge_base_id": kb_id,
                "query": "traditional Neapolitan pizza dough yeast fermentation",
                "top_k": 3,
                "mode": "hybrid"
            },
            headers=auth_headers
        )
        dt = (time.perf_counter() - t0) * 1000
        irrelevant_results = r.json().get("data", {}).get("results", []) if r.status_code == 200 else []
        record_result(
            "RAG Retrieval",
            "Irrelevant Query Handling",
            r.status_code == 200,
            dt,
            f"results_count={len(irrelevant_results)}"
        )

        # -------------------------------------------------------------
        # Full Chat & Answer-Generation E2E Tests
        # -------------------------------------------------------------
        # Document-grounded Question with Groq LLM
        t0 = time.perf_counter()
        r = await client.post(
            f"{API_BASE}/chat",
            json={
                "knowledge_base_id": kb_id,
                "prompt": "According to the uploaded documents, who leads Project Quantum Leap and what is its goal?",
                "top_k": 3
            },
            headers=auth_headers
        )
        dt = (time.perf_counter() - t0) * 1000
        chat_data = r.json().get("data", {}) if r.status_code == 200 else {}
        answer_text = chat_data.get("content", "")
        citations = chat_data.get("citations", [])
        status_val = chat_data.get("status")
        has_citations = len(citations) > 0
        grounded_correctly = ("Elena Rostova" in answer_text or "Rostova" in answer_text) and has_citations
        record_result(
            "Full Chat E2E",
            "Document-Grounded Answer with Valid Citations",
            r.status_code == 200 and grounded_correctly,
            dt,
            f"status={status_val}, citations={len(citations)}, preview={answer_text[:120].strip()}"
        )

        # General AI Question (no document hallucination)
        t0 = time.perf_counter()
        r = await client.post(
            f"{API_BASE}/chat",
            json={
                "knowledge_base_id": kb_id,
                "prompt": "What is the capital city of France?",
                "top_k": 3
            },
            headers=auth_headers
        )
        dt = (time.perf_counter() - t0) * 1000
        chat_data = r.json().get("data", {}) if r.status_code == 200 else {}
        answer_text = chat_data.get("content", "")
        citations = chat_data.get("citations", [])
        answer_type = chat_data.get("answer_type")
        record_result(
            "Full Chat E2E",
            "General Knowledge Question (No Hallucinated Citations)",
            r.status_code == 200 and "Paris" in answer_text and len(citations) == 0,
            dt,
            f"type={answer_type}, citations={len(citations)}, answer={answer_text[:80].strip()}"
        )

        # Insufficient evidence query
        t0 = time.perf_counter()
        r = await client.post(
            f"{API_BASE}/chat",
            json={
                "knowledge_base_id": kb_id,
                "prompt": "What is the exact internal vacation reimbursement policy for employees on Project Quantum Leap?",
                "top_k": 3
            },
            headers=auth_headers
        )
        dt = (time.perf_counter() - t0) * 1000
        chat_data = r.json().get("data", {}) if r.status_code == 200 else {}
        is_insufficient = chat_data.get("is_insufficient_evidence", False) or "insufficient" in chat_data.get("content", "").lower() or "not find" in chat_data.get("content", "").lower()
        record_result(
            "Full Chat E2E",
            "Missing Evidence Detection (Refuses to Hallucinate)",
            r.status_code == 200 and is_insufficient,
            dt,
            f"is_insufficient_flag={chat_data.get('is_insufficient_evidence')}, preview={chat_data.get('content', '')[:100]}"
        )

        # -------------------------------------------------------------
        # Database Integrity & Security Tests
        # -------------------------------------------------------------
        # SQL Injection defense check
        t0 = time.perf_counter()
        sqli_query = "'; DROP TABLE users; --"
        r = await client.post(
            f"{API_BASE}/retrieval/search",
            json={
                "knowledge_base_id": kb_id,
                "query": sqli_query,
                "top_k": 3
            },
            headers=auth_headers
        )
        dt = (time.perf_counter() - t0) * 1000
        async with async_session() as db:
            users_exist = (await db.execute(text("SELECT count(*) FROM users"))).scalar()
        record_result(
            "Security & DB Integrity",
            "SQL Injection Neutralization in Retrieval",
            r.status_code == 200 and users_exist > 0,
            dt,
            f"users_intact={users_exist}, status={r.status_code}"
        )

        # Cross-Tenant Isolation: Another user token cannot access User A's KB
        t0 = time.perf_counter()
        user_b_id = uuid.uuid4()
        user_b_email = f"virt_user_{user_b_id.hex[:6]}@test.local"
        async with async_session() as db:
            from app.infrastructure.database.models import User
            user_b = User(
                id=user_b_id,
                email=user_b_email,
                name="User B",
                password_hash="hashed_pw_virt",
                is_active=True,
                is_verified=True,
                role="USER"
            )
            db.add(user_b)
            await db.commit()

        from app.core.security import create_access_token
        token_b = create_access_token(user_id=user_b_id, role="USER")
        headers_b = {"Authorization": f"Bearer {token_b}"}

        # Try to access User A's KB as User B
        r_b = await client.get(f"{API_BASE}/knowledge-bases/{kb_id}", headers=headers_b)
        dt = (time.perf_counter() - t0) * 1000
        record_result(
            "Security & Tenant Isolation",
            "Cross-User Access Denial (User B cannot access User A KB)",
            r_b.status_code in (403, 404),
            dt,
            f"user_b_status={r_b.status_code}"
        )

        # -------------------------------------------------------------
        # Observability & Trace Verification
        # -------------------------------------------------------------
        t0 = time.perf_counter()
        r_traces = await client.get(f"{API_BASE}/observability/traces", headers=auth_headers)
        r_overview = await client.get(f"{API_BASE}/observability/overview", headers=auth_headers)
        dt = (time.perf_counter() - t0) * 1000
        traces_data = r_traces.json().get("data", {}) if r_traces.status_code == 200 else {}
        overview_data = r_overview.json().get("data", {}) if r_overview.status_code == 200 else {}
        trace_items = traces_data.get("items", [])
        record_result(
            "Observability & Tracing",
            "Real Trace Persistence & Latency/Token Logging",
            r_traces.status_code == 200 and len(trace_items) > 0,
            dt,
            f"traces_count={len(trace_items)}, total_requests={overview_data.get('total_requests')}, latest_duration={trace_items[0].get('duration_ms') if trace_items else 0}ms"
        )

        # -------------------------------------------------------------
        # Teardown: Remove synthetic test records only
        # -------------------------------------------------------------
        t0 = time.perf_counter()
        del_r = await client.delete(f"{API_BASE}/knowledge-bases/{kb_id}", headers=auth_headers)
        async with async_session() as db:
            await db.execute(text("DELETE FROM users WHERE id = :id"), {"id": user_b_id})
            await db.commit()
            kb_left = (await db.execute(text("SELECT count(*) FROM knowledge_bases WHERE id = :id"), {"id": kb_id})).scalar()
            chunks_left = (await db.execute(text("SELECT count(*) FROM document_chunks WHERE document_id = :id"), {"id": doc_id})).scalar()
        dt = (time.perf_counter() - t0) * 1000
        record_result(
            "Safe Cleanup",
            "Isolated Test Records Teardown (0 Leftover Records)",
            del_r.status_code in (200, 204) and kb_left == 0 and chunks_left == 0,
            dt,
            f"kb_left={kb_left}, chunks_left={chunks_left}"
        )

    print("\n" + "=" * 70)
    print(f"LIVE TEST EXECUTION COMPLETE: {results['passed']}/{results['total']} PASSED, {results['failed']} FAILED")
    print("=" * 70)
    return results

if __name__ == "__main__":
    res = asyncio.run(run_live_tests())
    if res["failed"] > 0:
        sys.exit(1)
    sys.exit(0)
