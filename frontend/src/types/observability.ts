export interface ChunkScoreProvenance {
  chunk_id: string;
  document_id?: string;
  vector_score?: number | null;
  bm25_score?: number | null;
  rrf_score?: number | null;
  rerank_score?: number | null;
  final_rank?: number;
  retrieval_stage: string;
  is_used_in_generation: boolean;
  is_cited: boolean;
}

export interface TraceStepItem {
  id: string;
  name: string;
  stepType:
    | 'gateway'
    | 'retrieval'
    | 'dense_retrieval'
    | 'lexical_retrieval'
    | 'fusion'
    | 'rerank'
    | 'reranking'
    | 'llm'
    | 'grounded_generation'
    | 'verification'
    | 'citation_validation'
    | 'self_healing'
    | 'recovery'
    | 'completion'
    | string;
  durationMs: number | null;
  status: 'completed' | 'failed' | 'recovered' | 'skipped' | 'pending';
  inputs?: Record<string, unknown>;
  outputs?: Record<string, unknown>;
  errorCode?: string | null;
  errorMessage?: string | null;
  metadata?: Record<string, unknown>;
  promptTokens?: number | null;
  completionTokens?: number | null;
  estimatedCostUsd?: number | null;
  isSkipped?: boolean;
}

export interface TraceRunItem {
  id: string;
  traceId?: string;
  requestId?: string;
  query: string;
  status: 'completed' | 'success' | 'failed' | 'recovered' | string;
  durationMs: number | null;
  tokensTotal: number | null;
  promptTokens?: number | null;
  completionTokens?: number | null;
  estimatedCostUsd?: number | null;
  costStatus?: 'estimated' | 'provider_reported' | 'unavailable' | string;
  costCurrency?: string;
  pricingSource?: string | null;
  model: string;
  retrievalMethod?: string | null;
  retrievalScores?: ChunkScoreProvenance[];
  evidenceSufficiency?: string | null;
  citationValidationPassed?: boolean | null;
  verificationStatus?: string | null;
  errorCategory?: string | null;
  recoveryCount?: number;
  createdAt: string;
  steps?: TraceStepItem[];
  metadata?: Record<string, unknown>;
}

export interface ReliabilityMetrics {
  total_requests: number;
  successful_requests: number;
  failed_requests: number;
  recovered_requests: number;
  error_rate: number;
  avg_latency_ms: number | null;
  p50_latency_ms: number | null;
  p95_latency_ms: number | null;
  p99_latency_ms: number | null;
  retrieval_latency_ms: number | null;
  reranking_latency_ms: number | null;
  generation_latency_ms: number | null;
  citation_validation_latency_ms: number | null;
  recovery_latency_ms: number | null;
  timeout_count: number;
  retry_count: number;
  insufficient_evidence_count: number;
  empty_retrieval_count: number;
  citation_validation_failure_count: number;
  workflow_completion_rate: number;
  workflow_failure_rate: number;
  llm_provider_error_count: number;
  embedding_provider_error_count: number;
  database_error_count: number;
  stage_breakdown: Record<string, number>;
}

export interface AlertRecord {
  id: string;
  name: string;
  severity: 'critical' | 'warning' | 'info';
  condition: string;
  threshold: number | string;
  current_value: number | string;
  status: 'active' | 'cooldown' | 'resolved';
  triggered_at: string;
  message: string;
  category: string;
}

export interface OverviewStats {
  total_requests: number;
  successful_requests: number;
  failed_requests: number;
  recovered_requests: number;
  success_rate: number;
  error_rate: number;
  p50_latency_ms: number | null;
  p95_latency_ms: number | null;
  p99_latency_ms: number | null;
  avg_latency_ms: number | null;
  total_tokens: number;
  prompt_tokens: number;
  completion_tokens: number;
  total_estimated_cost_usd: number | null;
  avg_cost_per_query_usd: number | null;
  cost_status: 'estimated' | 'provider_reported' | 'unavailable' | string;
  cost_currency: string;
  models_used: Record<string, number>;
  retrieval_methods_used: Record<string, number>;
  recovery_attempts: number;
  recovery_success_count: number;
}

export interface ErrorIncidentItem {
  trace_id: string;
  query: string;
  created_at: string;
  duration_ms: number | null;
  error_category: string;
  safe_code: string;
  diagnostic_summary: string;
  affected_stage: string;
  is_retryable: boolean;
  recovery_succeeded: boolean;
  suggested_action: string;
  is_infrastructure_failure: boolean;
}

export interface ModelPricingItem {
  model_id: string;
  provider: string;
  input_cost_per_1m: number;
  output_cost_per_1m: number;
  currency: string;
  pricing_source: string;
  last_updated: string;
}
