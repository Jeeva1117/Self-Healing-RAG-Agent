export type DocumentStatus = 'not_indexed' | 'pending' | 'ready' | 'failed';
export type DocumentFileType = 'pdf' | 'docx' | 'txt' | 'csv' | 'md' | 'url';

export interface DocumentItem {
  id: string;
  name: string;
  type: DocumentFileType;
  size: string;
  status: DocumentStatus;
  chunksCount: number | null;
  updatedAt: string;
  source: string;
  collection: string;
  metadata?: Record<string, unknown>;
}
