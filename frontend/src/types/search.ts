export type RetrievalMode = 'hybrid' | 'vector' | 'lexical';

export interface RetrievalRequest {
  knowledge_base_id: string;
  query: string;
  mode?: RetrievalMode;
  retrieval_mode?: RetrievalMode;
  enable_reranking?: boolean;
  reranking_required?: boolean;
  candidate_limit?: number;
  candidate_k?: number;
  top_k?: number;
  similarity_threshold?: number;
  rrf_k?: number;
}

export interface RetrievalResultItem {
  chunk_id: string;
  document_id: string;
  document_version_id?: string | null;
  document_name: string;
  content: string;
  page_number: number | null;
  section_title: string | null;
  chunk_index: number;
  token_count: number | null;
  character_count: number;
  metadata: Record<string, unknown>;
  vector_rank: number | null;
  vector_score: number | null;
  semantic_rank?: number | null;
  semantic_score?: number | null;
  lexical_rank: number | null;
  lexical_score: number | null;
  keyword_rank?: number | null;
  bm25_score?: number | null;
  rrf_rank: number | null;
  rrf_score: number | null;
  reranker_rank: number | null;
  reranker_score: number | null;
  rerank_score?: number | null;
  final_rank: number;
  stage_provenance: 'hybrid' | 'vector' | 'lexical' | string;
}

export interface RetrievalLatencyBreakdown {
  vector_ms: number;
  lexical_ms: number;
  fusion_ms: number;
  rerank_ms: number;
  total_ms: number;
}

export interface RetrievalResponse {
  query: string;
  knowledge_base_id: string;
  mode: string;
  retrieval_mode?: string;
  enable_reranking: boolean;
  reranking_enabled?: boolean;
  reranking_applied?: boolean;
  candidate_count: number;
  returned_count: number;
  total_results?: number;
  results: RetrievalResultItem[];
  latency: RetrievalLatencyBreakdown;
  latency_ms?: number;
  warnings?: string[];
}

export interface ComparisonResponse {
  query: string;
  knowledge_base_id: string;
  vector_results: RetrievalResultItem[];
  lexical_results: RetrievalResultItem[];
  hybrid_results: RetrievalResultItem[];
  latency: RetrievalLatencyBreakdown;
  warnings?: string[];
}

