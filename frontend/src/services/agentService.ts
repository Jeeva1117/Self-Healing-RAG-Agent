import { apiClient } from './api';
import type { ChatResponseData, SendChatRequest } from '@/types/chat';

interface ApiResponse<T> {
  success: boolean;
  data: T;
  error?: {
    code: string;
    message: string;
    details?: unknown;
  };
}

export interface GraphTopologyNode {
  id: string;
  name: string;
  role: string;
  phase: string;
}

export interface GraphTopologyEdge {
  from: string;
  condition: string;
  branches: string[];
}

export interface GraphTopology {
  graph_id: string;
  framework: string;
  framework_version: string;
  status: string;
  recursion_limit: number;
  max_retries: number;
  nodes: GraphTopologyNode[];
  conditional_edges: GraphTopologyEdge[];
}

export const agentService = {
  /**
   * Executes real LangGraph workflow simulation via POST /api/v1/agents/simulate
   */
  simulateWorkflow: async (request: SendChatRequest): Promise<ChatResponseData> => {
    const res = await apiClient<ApiResponse<ChatResponseData>>('/agents/simulate', {
      method: 'POST',
      body: JSON.stringify(request),
    });
    return res.data;
  },

  /**
   * Executes production LangGraph workflow via POST /api/v1/agents/run
   */
  runWorkflow: async (request: SendChatRequest): Promise<ChatResponseData> => {
    const res = await apiClient<ApiResponse<ChatResponseData>>('/agents/run', {
      method: 'POST',
      body: JSON.stringify(request),
    });
    return res.data;
  },

  /**
   * Executes multi-agent collaborative LangGraph workflow via POST /api/v1/agents/collaborate
   */
  collaborateWorkflow: async (request: SendChatRequest): Promise<ChatResponseData> => {
    const res = await apiClient<ApiResponse<ChatResponseData>>('/agents/collaborate', {
      method: 'POST',
      body: JSON.stringify(request),
    });
    return res.data;
  },

  /**
   * Fetches active LangGraph topology metadata via GET /api/v1/agents/graph
   */
  getGraphTopology: async (): Promise<GraphTopology> => {
    const res = await apiClient<ApiResponse<GraphTopology>>('/agents/graph');
    return res.data;
  },
};
