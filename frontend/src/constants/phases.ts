export interface PhaseInfo {
  number: number;
  title: string;
  description: string;
  status: 'completed' | 'in_progress' | 'upcoming';
}

export const SYSTEM_PHASES: PhaseInfo[] = [
  {
    number: 1,
    title: 'Foundation & Architecture',
    description: 'Clean layered architecture, FastAPI 0.115, React 19, SQLAlchemy 2 async, Redis client, Health/Readiness probes.',
    status: 'completed',
  },
  {
    number: 2,
    title: 'Professional Production UI/UX',
    description: 'Complete design system, themes, dashboard widgets, responsive navigation.',
    status: 'upcoming',
  },
  {
    number: 3,
    title: 'Authentication & Multi-Tenancy',
    description: 'JWT authentication, RBAC, workspaces, team permissions.',
    status: 'upcoming',
  },
  {
    number: 4,
    title: 'Knowledge Base & Ingestion',
    description: 'Document parsers, semantic chunkers, metadata extraction, S3/MinIO storage.',
    status: 'upcoming',
  },
  {
    number: 5,
    title: 'Hybrid Retrieval & Reranking',
    description: 'BM25 + pgvector cosine search, reciprocal rank fusion (RRF), cross-encoder reranking.',
    status: 'upcoming',
  },
  {
    number: 6,
    title: 'Generation & Citations',
    description: 'Streaming LLM answers, sentence-level attribution, citation source cards.',
    status: 'upcoming',
  },
  {
    number: 7,
    title: 'Agentic RAG (LangGraph)',
    description: 'State graph workflows, routing, fallback decision trees, tool execution.',
    status: 'upcoming',
  },
  {
    number: 8,
    title: 'Self-Healing Engine',
    description: 'Failure detection, query reformulations, sub-query decomposition, retrieval expansion.',
    status: 'upcoming',
  },
  {
    number: 9,
    title: 'Verification & Guardrails',
    description: 'Claim validation, hallucination detection, prompt injection shielding.',
    status: 'upcoming',
  },
  {
    number: 10,
    title: 'Evaluation Suite',
    description: 'RAGAS & DeepEval metrics, precision/recall synthetic test suites.',
    status: 'upcoming',
  },
  {
    number: 11,
    title: 'Observability & Tracing',
    description: 'OpenTelemetry, LangSmith traces, latency breakdowns, token spend monitoring.',
    status: 'upcoming',
  },
  {
    number: 12,
    title: 'Production Hardening',
    description: 'Rate limiting, cache optimization, horizontal scaling, audit compliance.',
    status: 'upcoming',
  },
];
