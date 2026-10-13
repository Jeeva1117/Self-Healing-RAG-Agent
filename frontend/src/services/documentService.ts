import { apiClient } from './api';
import type { DocumentItem } from '@/types/document';

export const documentService = {
  // Pre-configured contract for Phase 4
  getDocuments: async (): Promise<DocumentItem[]> => {
    return apiClient<DocumentItem[]>('/documents');
  },

  uploadDocument: async (file: File): Promise<DocumentItem> => {
    const formData = new FormData();
    formData.append('file', file);
    return apiClient<DocumentItem>('/documents/upload', {
      method: 'POST',
      body: formData,
    });
  },
};
