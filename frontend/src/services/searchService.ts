import { apiClient } from './api';
import type {
  ComparisonResponse,
  RetrievalRequest,
  RetrievalResponse,
} from '@/types/search';

interface ApiResponse<T> {
  success: boolean;
  data: T;
  error?: {
    code: string;
    message: string;
    details?: unknown;
  };
}

export const searchService = {
  /**
   * Executes semantic vector, BM25 lexical, or RRF hybrid search with optional reranking.
   */
  search: async (request: RetrievalRequest): Promise<RetrievalResponse> => {
    const res = await apiClient<ApiResponse<RetrievalResponse>>('/retrieval/search', {
      method: 'POST',
      body: JSON.stringify(request),
    });
    return res.data;
  },

  /**
   * Executes Vector, Lexical, and Hybrid retrieval in parallel for side-by-side comparison.
   */
  compare: async (request: RetrievalRequest): Promise<ComparisonResponse> => {
    const res = await apiClient<ApiResponse<ComparisonResponse>>('/retrieval/compare', {
      method: 'POST',
      body: JSON.stringify(request),
    });
    return res.data;
  },
};
