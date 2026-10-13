import { apiClient } from './api';
import type {
  DocumentChunkListResponse,
  DocumentItem,
  DocumentListResponse,
  KnowledgeBase,
  KnowledgeBaseListResponse,
} from '@/types/knowledgeBase';

interface ApiResponse<T> {
  success: boolean;
  data: T;
  error?: {
    code: string;
    message: string;
    details?: unknown;
  };
}

export const knowledgeBaseService = {
  // Knowledge Base CRUD
  listKnowledgeBases: async (offset = 0, limit = 50): Promise<KnowledgeBaseListResponse> => {
    const res = await apiClient<ApiResponse<KnowledgeBaseListResponse>>(
      `/knowledge-bases?offset=${offset}&limit=${limit}`
    );
    return res.data;
  },

  getKnowledgeBase: async (id: string): Promise<KnowledgeBase> => {
    const res = await apiClient<ApiResponse<KnowledgeBase>>(`/knowledge-bases/${id}`);
    return res.data;
  },

  createKnowledgeBase: async (data: { name: string; description?: string }): Promise<KnowledgeBase> => {
    const res = await apiClient<ApiResponse<KnowledgeBase>>('/knowledge-bases', {
      method: 'POST',
      body: JSON.stringify(data),
    });
    return res.data;
  },

  updateKnowledgeBase: async (
    id: string,
    data: { name?: string; description?: string; status?: string }
  ): Promise<KnowledgeBase> => {
    const res = await apiClient<ApiResponse<KnowledgeBase>>(`/knowledge-bases/${id}`, {
      method: 'PATCH',
      body: JSON.stringify(data),
    });
    return res.data;
  },

  deleteKnowledgeBase: async (id: string): Promise<void> => {
    await apiClient<ApiResponse<{ message: string }>>(`/knowledge-bases/${id}`, {
      method: 'DELETE',
    });
  },

  // Document Operations
  uploadDocument: async (kbId: string, file: File): Promise<DocumentItem> => {
    const formData = new FormData();
    formData.append('file', file);
    const res = await apiClient<ApiResponse<DocumentItem>>(`/knowledge-bases/${kbId}/documents`, {
      method: 'POST',
      body: formData,
    });
    return res.data;
  },

  listDocuments: async (kbId: string, offset = 0, limit = 50): Promise<DocumentListResponse> => {
    const res = await apiClient<ApiResponse<DocumentListResponse>>(
      `/knowledge-bases/${kbId}/documents?offset=${offset}&limit=${limit}`
    );
    return res.data;
  },

  getDocument: async (id: string): Promise<DocumentItem> => {
    const res = await apiClient<ApiResponse<DocumentItem>>(`/documents/${id}`);
    return res.data;
  },

  getDocumentChunks: async (
    documentId: string,
    offset = 0,
    limit = 50
  ): Promise<DocumentChunkListResponse> => {
    const res = await apiClient<ApiResponse<DocumentChunkListResponse>>(
      `/documents/${documentId}/chunks?offset=${offset}&limit=${limit}`
    );
    return res.data;
  },

  deleteDocument: async (id: string): Promise<void> => {
    await apiClient<ApiResponse<{ message: string }>>(`/documents/${id}`, {
      method: 'DELETE',
    });
  },

  reprocessDocument: async (id: string): Promise<{ document_id: string; status: string; message: string }> => {
    const res = await apiClient<ApiResponse<{ document_id: string; status: string; message: string }>>(
      `/documents/${id}/reprocess`,
      {
        method: 'POST',
      }
    );
    return res.data;
  },

  // Phase 12: Knowledge Base Management & Intelligence API Client
  getHealth: async (kbId: string) => {
    const res = await apiClient<ApiResponse<import('@/types/knowledgeBase').KnowledgeBaseHealthReport>>(
      `/knowledge-bases/${kbId}/health`
    );
    return res.data;
  },

  getDocumentHealth: async (kbId: string, docId: string) => {
    const res = await apiClient<ApiResponse<import('@/types/knowledgeBase').DocumentHealthReport>>(
      `/knowledge-bases/${kbId}/documents/${docId}/health`
    );
    return res.data;
  },

  getDuplicates: async (kbId: string, threshold = 0.85) => {
    const res = await apiClient<ApiResponse<import('@/types/knowledgeBase').DuplicateReport>>(
      `/knowledge-bases/${kbId}/duplicates?threshold=${threshold}`
    );
    return res.data;
  },

  getCoverage: async (kbId: string) => {
    const res = await apiClient<ApiResponse<import('@/types/knowledgeBase').CoverageReport>>(
      `/knowledge-bases/${kbId}/coverage`
    );
    return res.data;
  },

  getConflicts: async (kbId: string) => {
    const res = await apiClient<ApiResponse<import('@/types/knowledgeBase').ConflictReport>>(
      `/knowledge-bases/${kbId}/conflicts`
    );
    return res.data;
  },

  getDocumentVersions: async (kbId: string, docId: string) => {
    const res = await apiClient<ApiResponse<import('@/types/knowledgeBase').DocumentVersionHistoryResponse>>(
      `/knowledge-bases/${kbId}/documents/${docId}/versions`
    );
    return res.data;
  },

  reindexDocument: async (kbId: string, docId: string) => {
    const res = await apiClient<ApiResponse<import('@/types/knowledgeBase').DocumentVersionItem>>(
      `/knowledge-bases/${kbId}/documents/${docId}/reindex`,
      {
        method: 'POST',
      }
    );
    return res.data;
  },

  repairDocument: async (
    kbId: string,
    docId: string,
    body: import('@/types/knowledgeBase').RepairActionRequest
  ) => {
    const res = await apiClient<ApiResponse<import('@/types/knowledgeBase').RepairJobResponse>>(
      `/knowledge-bases/${kbId}/documents/${docId}/repair`,
      {
        method: 'POST',
        body: JSON.stringify(body),
      }
    );
    return res.data;
  },

  getRepairJob: async (kbId: string, jobId: string) => {
    const res = await apiClient<ApiResponse<import('@/types/knowledgeBase').RepairJobResponse>>(
      `/knowledge-bases/${kbId}/repair-jobs/${jobId}`
    );
    return res.data;
  },

  listRepairJobs: async (kbId: string) => {
    const res = await apiClient<ApiResponse<import('@/types/knowledgeBase').RepairJobResponse[]>>(
      `/knowledge-bases/${kbId}/repair-jobs`
    );
    return res.data;
  },
};

