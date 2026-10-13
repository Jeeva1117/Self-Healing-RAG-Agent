export interface RetrievalMetrics {
  precision_at_k: Record<number, number>;
  recall_at_k: Record<number, number>;
  mrr: number;
  ndcg_at_k: Record<number, number>;
  chunk_coverage: number;
  empty_retrieval: boolean;
  retrieval_latency_ms: number;
}

export interface AnswerMetrics {
  groundedness_score: number;
  key_fact_coverage: number;
  citation_validity_score: number;
  claim_support_score: number;
  unsupported_claims_count: number;
  correct_insufficient_handling: boolean;
  relevance_score: number;
  completeness_score: number;
}

export interface SelfHealingMetrics {
  recovery_attempted: boolean;
  recovery_count: number;
  initial_failure_category?: string | null;
  recovery_action?: string | null;
  recovery_outcome?: string | null;
  retrieval_improved: boolean;
  answer_improved: boolean;
  recovery_latency_ms: number;
  is_budget_exhausted: boolean;
  cycle_detected: boolean;
}

export interface CaseEvaluationResult {
  test_case_id: string;
  category: string;
  passed: boolean;
  status: string;
  failure_reasons: string[];
  query: string;
  retrieval_metrics: RetrievalMetrics;
  answer_metrics: AnswerMetrics;
  recovery_metrics: SelfHealingMetrics;
  actual_response_summary: string;
  total_latency_ms: number;
}

export interface BaselineComparison {
  baseline_run_id: string;
  is_compatible: boolean;
  warning?: string | null;
  improvements: Record<string, number>;
  regressions: Record<string, number>;
  unchanged: Record<string, number>;
  missing_metrics: string[];
}

export interface EvaluationRunDetailResponse {
  id: string;
  name: string;
  dataset_name: string;
  dataset_version: string;
  status: string;
  total_cases: number;
  passed_cases: number;
  failed_cases: number;
  pass_rate: number;
  created_at: string;
  summary_metrics: Record<string, any>;
  run_config?: Record<string, any> | null;
  case_results: CaseEvaluationResult[];
  baseline_comparison?: BaselineComparison | null;
}

export interface EvaluationRunListItem {
  id: string;
  name: string;
  dataset_name: string;
  dataset_version: string;
  status: string;
  total_cases: number;
  passed_cases: number;
  failed_cases: number;
  pass_rate: number;
  created_at: string;
  summary_metrics: Record<string, any>;
}

export interface EvaluationDatasetItem {
  name: string;
  version: string;
  case_count: number;
  description: string;
}

export interface EvaluationSummaryStats {
  total_runs: number;
  average_pass_rate: number;
  average_groundedness: number;
  average_precision_at_5: number;
  average_recall_at_5: number;
  average_mrr: number;
  recovery_success_rate: number;
  latest_run_id?: string | null;
}

export interface TriggerEvaluationRequest {
  name?: string;
  dataset_name?: string;
  dataset_version?: string;
  knowledge_base_id?: string;
  k_values?: number[];
  baseline_run_id?: string;
}
