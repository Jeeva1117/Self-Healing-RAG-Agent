import { apiClient } from '@/services/api';
import type { HealthResponse, ReadinessResponse, SystemInfoResponse } from '@/types/health';

export const healthService = {
  getHealth: async (): Promise<HealthResponse> => {
    return apiClient<HealthResponse>('/health');
  },

  getReadiness: async (): Promise<ReadinessResponse> => {
    return apiClient<ReadinessResponse>('/health/ready');
  },

  getSystemInfo: async (): Promise<SystemInfoResponse> => {
    return apiClient<SystemInfoResponse>('/system/info');
  },
};
