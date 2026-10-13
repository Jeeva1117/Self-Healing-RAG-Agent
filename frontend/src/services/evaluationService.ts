import { apiClient } from './api';
import type {
  BaselineComparison,
  EvaluationDatasetItem,
  EvaluationRunDetailResponse,
  EvaluationRunListItem,
  EvaluationSummaryStats,
  TriggerEvaluationRequest,
} from '@/types/evaluation';

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

export const evaluationService = {
  /**
   * Retrieves all registered golden evaluation test datasets
   */
  listDatasets: async (): Promise<EvaluationDatasetItem[]> => {
    const res = await apiClient<ApiResponse<EvaluationDatasetItem[]>>('/evaluation/datasets');
    return res.data;
  },

  /**
   * Lists past evaluation benchmark runs
   */
  listRuns: async (limit: number = 20): Promise<EvaluationRunListItem[]> => {
    const res = await apiClient<ApiResponse<EvaluationRunListItem[]>>(`/evaluation/runs?limit=${limit}`);
    return res.data;
  },

  /**
   * Retrieves full details and case breakdown of an individual run
   */
  getRun: async (runId: string): Promise<EvaluationRunDetailResponse> => {
    const res = await apiClient<ApiResponse<EvaluationRunDetailResponse>>(`/evaluation/runs/${runId}`);
    return res.data;
  },

  /**
   * Triggers a live evaluation run against current pipeline
   */
  triggerRun: async (payload: TriggerEvaluationRequest): Promise<EvaluationRunDetailResponse> => {
    const res = await apiClient<ApiResponse<EvaluationRunDetailResponse>>('/evaluation/runs', {
      method: 'POST',
      body: JSON.stringify(payload),
    });
    return res.data;
  },

  /**
   * Compares candidate run against baseline
   */
  compareRuns: async (runId: string, baselineRunId: string): Promise<BaselineComparison> => {
    const res = await apiClient<ApiResponse<BaselineComparison>>(
      `/evaluation/runs/${runId}/compare/${baselineRunId}`
    );
    return res.data;
  },

  /**
   * Gets aggregated quality intelligence summary statistics
   */
  getSummaryStats: async (): Promise<EvaluationSummaryStats> => {
    const res = await apiClient<ApiResponse<EvaluationSummaryStats>>('/evaluation/metrics/summary');
    return res.data;
  },
};
