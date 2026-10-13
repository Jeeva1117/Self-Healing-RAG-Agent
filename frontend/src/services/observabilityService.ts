import { apiClient } from './api';
import type {
  AlertRecord,
  ChunkScoreProvenance,
  ErrorIncidentItem,
  ModelPricingItem,
  OverviewStats,
  ReliabilityMetrics,
  TraceRunItem,
  TraceStepItem,
} from '@/types/observability';

interface ApiResponse<T> {
  success: boolean;
  data: T;
  message?: string;
  error?: {
    code: string;
    message: string;
    details?: unknown;
  };
}

interface RawSpan {
  span_id: string;
  parent_span_id?: string | null;
  trace_id: string;
  name: string;
  step_type: string;
  status: string;
  start_time: number;
  end_time: number;
  duration_ms: number;
  inputs?: Record<string, unknown>;
  outputs?: Record<string, unknown>;
  error_code?: string | null;
  error_message?: string | null;
  metadata?: Record<string, unknown>;
  prompt_tokens?: number | null;
  completion_tokens?: number | null;
  estimated_cost_usd?: number | null;
  is_skipped?: boolean;
}

interface RawTrace {
  trace_id: string;
  request_id?: string | null;
  user_id?: string | null;
  knowledge_base_id?: string | null;
  query: string;
  status: string;
  duration_ms: number;
  tokens_total: number;
  prompt_tokens?: number | null;
  completion_tokens?: number | null;
  estimated_cost_usd?: number | null;
  cost_status?: string;
  cost_currency?: string;
  pricing_source?: string | null;
  model: string;
  retrieval_method?: string | null;
  retrieval_scores?: ChunkScoreProvenance[];
  evidence_sufficiency?: string | null;
  citation_validation_passed?: boolean | null;
  verification_status?: string | null;
  error_category?: string | null;
  recovery_count?: number;
  created_at: string;
  spans?: RawSpan[];
  metadata?: Record<string, unknown>;
}

function mapSpan(sp: RawSpan): TraceStepItem {
  return {
    id: sp.span_id,
    name: sp.name,
    stepType: sp.step_type,
    durationMs: sp.duration_ms,
    status: (sp.status as TraceStepItem['status']) || 'completed',
    inputs: sp.inputs,
    outputs: sp.outputs,
    errorCode: sp.error_code,
    errorMessage: sp.error_message,
    metadata: sp.metadata,
    promptTokens: sp.prompt_tokens,
    completionTokens: sp.completion_tokens,
    estimatedCostUsd: sp.estimated_cost_usd,
    isSkipped: sp.is_skipped,
  };
}

function mapTrace(rt: RawTrace): TraceRunItem {
  return {
    id: rt.trace_id,
    traceId: rt.trace_id,
    requestId: rt.request_id || undefined,
    query: rt.query,
    status: rt.status,
    durationMs: rt.duration_ms,
    tokensTotal: rt.tokens_total,
    promptTokens: rt.prompt_tokens,
    completionTokens: rt.completion_tokens,
    estimatedCostUsd: rt.estimated_cost_usd,
    costStatus: rt.cost_status,
    costCurrency: rt.cost_currency,
    pricingSource: rt.pricing_source,
    model: rt.model,
    retrievalMethod: rt.retrieval_method,
    retrievalScores: rt.retrieval_scores,
    evidenceSufficiency: rt.evidence_sufficiency,
    citationValidationPassed: rt.citation_validation_passed,
    verificationStatus: rt.verification_status,
    errorCategory: rt.error_category,
    recoveryCount: rt.recovery_count,
    createdAt: rt.created_at,
    steps: (rt.spans || []).map(mapSpan),
    metadata: rt.metadata,
  };
}

export const observabilityService = {
  /**
   * Retrieves paginated traces with optional status and query filtering
   */
  listTraces: async (params?: {
    limit?: number;
    offset?: number;
    status?: string;
    search?: string;
  }): Promise<{ items: TraceRunItem[]; total: number }> => {
    const query = new URLSearchParams();
    if (params?.limit) query.set('limit', String(params.limit));
    if (params?.offset) query.set('offset', String(params.offset));
    if (params?.status && params.status !== 'all') query.set('status', params.status);
    if (params?.search) query.set('search', params.search);

    const qs = query.toString() ? `?${query.toString()}` : '';
    const res = await apiClient<ApiResponse<{ items: RawTrace[]; total: number; limit: number; offset: number }>>(
      `/observability/traces${qs}`
    );

    return {
      items: (res.data.items || []).map(mapTrace),
      total: res.data.total || 0,
    };
  },

  /**
   * Retrieves single trace details and waterfall spans
   */
  getTrace: async (traceId: string): Promise<TraceRunItem> => {
    const res = await apiClient<ApiResponse<RawTrace>>(`/observability/traces/${traceId}`);
    return mapTrace(res.data);
  },

  /**
   * Calculates live reliability metrics and latency percentiles
   */
  getMetrics: async (): Promise<ReliabilityMetrics> => {
    const res = await apiClient<ApiResponse<ReliabilityMetrics>>('/observability/metrics');
    return res.data;
  },

  /**
   * Phase 11 Overview KPIs (tokens, costs, models, success rates)
   */
  getOverview: async (): Promise<OverviewStats> => {
    const res = await apiClient<ApiResponse<OverviewStats>>('/observability/overview');
    return res.data;
  },

  /**
   * Phase 11 Error Explorer (failure taxonomy, root cause, suggested actions)
   */
  getErrorExplorer: async (limit: number = 50): Promise<ErrorIncidentItem[]> => {
    const res = await apiClient<ApiResponse<ErrorIncidentItem[]>>(`/observability/errors?limit=${limit}`);
    return res.data;
  },

  /**
   * Model Pricing Catalog (cost per million tokens and currency)
   */
  getPricingCatalog: async (): Promise<ModelPricingItem[]> => {
    const res = await apiClient<ApiResponse<ModelPricingItem[]>>('/observability/pricing');
    return res.data;
  },

  /**
   * Evaluates rules against live metrics and returns active & past alerts
   */
  getAlerts: async (): Promise<AlertRecord[]> => {
    const res = await apiClient<ApiResponse<AlertRecord[]>>('/observability/alerts');
    return res.data;
  },

  /**
   * Queries downstream readiness probe
   */
  getReadiness: async (): Promise<{ status: string; dependencies?: Record<string, unknown> }> => {
    const res = await apiClient<{ status: string; dependencies?: Record<string, unknown> }>('/observability/health/ready');
    return res;
  },
};
