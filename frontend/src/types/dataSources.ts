export type DataSourceType = 'local' | 'web' | 'github' | 'gdrive' | 'notion' | 'postgres';

export type DataSourceStatus =
  | 'not_configured'
  | 'setup_required'
  | 'disconnected'
  | 'connected'
  | 'syncing'
  | 'ready'
  | 'partial_failure'
  | 'failed';

export interface DataSourceItem {
  id: string;
  user_id: string;
  knowledge_base_id?: string | null;
  source_type: DataSourceType;
  name: string;
  description?: string | null;
  config: Record<string, any>;
  status: DataSourceStatus;
  last_sync_at?: string | null;
  last_sync_status?: string | null;
  last_sync_error?: string | null;
  synced_documents_count: number;
  synced_chunks_count: number;
  created_at: string;
  updated_at: string;
}

export interface ConnectorCatalogItem {
  source_type: DataSourceType;
  name: string;
  description: string;
  icon: string;
  requires_auth: boolean;
  auth_type: string;
  configured_count: number;
  active_status: DataSourceStatus | 'configured';
  setup_guide: string;
}

export interface ConnectionTestResult {
  success: boolean;
  message: string;
  details: Record<string, any>;
  can_browse: boolean;
}

export interface SourceItem {
  id: string;
  name: string;
  item_type: string;
  size_bytes?: number | null;
  path?: string | null;
  mime_type?: string | null;
  url?: string | null;
  selectable: boolean;
  metadata: Record<string, any>;
}

export interface SyncResult {
  success: boolean;
  source_id: string;
  knowledge_base_id: string;
  documents_created: number;
  documents_updated: number;
  chunks_created: number;
  errors: string[];
  synced_items: string[];
}
