import { apiClient } from './api';
import type {
  ConnectionTestResult,
  ConnectorCatalogItem,
  DataSourceItem,
  SourceItem,
  SyncResult,
} from '@/types/dataSources';

interface ApiResponse<T> {
  success: boolean;
  data: T;
  error?: {
    code: string;
    message: string;
    details?: unknown;
  };
}

export const dataSourcesService = {
  getCatalog: async (): Promise<ConnectorCatalogItem[]> => {
    const res = await apiClient<ApiResponse<ConnectorCatalogItem[]>>('/data-sources/catalog');
    return res.data;
  },

  listDataSources: async (sourceType?: string): Promise<DataSourceItem[]> => {
    const query = sourceType ? `?source_type=${sourceType}` : '';
    const res = await apiClient<ApiResponse<DataSourceItem[]>>(`/data-sources${query}`);
    return res.data;
  },

  getDataSource: async (id: string): Promise<DataSourceItem> => {
    const res = await apiClient<ApiResponse<DataSourceItem>>(`/data-sources/${id}`);
    return res.data;
  },

  createDataSource: async (payload: {
    source_type: string;
    name: string;
    description?: string;
    knowledge_base_id?: string | null;
    config: Record<string, any>;
  }): Promise<DataSourceItem> => {
    const res = await apiClient<ApiResponse<DataSourceItem>>('/data-sources', {
      method: 'POST',
      body: JSON.stringify(payload),
    });
    return res.data;
  },

  updateDataSource: async (
    id: string,
    payload: {
      name?: string;
      description?: string;
      knowledge_base_id?: string | null;
      config?: Record<string, any>;
    }
  ): Promise<DataSourceItem> => {
    const res = await apiClient<ApiResponse<DataSourceItem>>(`/data-sources/${id}`, {
      method: 'PUT',
      body: JSON.stringify(payload),
    });
    return res.data;
  },

  deleteDataSource: async (id: string): Promise<void> => {
    await apiClient<ApiResponse<{ success: boolean }>>(`/data-sources/${id}`, {
      method: 'DELETE',
    });
  },

  testConnection: async (id: string): Promise<ConnectionTestResult> => {
    const res = await apiClient<ApiResponse<ConnectionTestResult>>(`/data-sources/${id}/test`, {
      method: 'POST',
    });
    return res.data;
  },

  listSourceItems: async (id: string, parentId?: string): Promise<SourceItem[]> => {
    const query = parentId ? `?parent_id=${encodeURIComponent(parentId)}` : '';
    const res = await apiClient<ApiResponse<SourceItem[]>>(`/data-sources/${id}/items${query}`);
    return res.data;
  },

  syncDataSource: async (
    id: string,
    payload: { selected_ids: string[]; knowledge_base_id?: string }
  ): Promise<SyncResult> => {
    const res = await apiClient<ApiResponse<SyncResult>>(`/data-sources/${id}/sync`, {
      method: 'POST',
      body: JSON.stringify(payload),
    });
    return res.data;
  },
};
