export type KnowledgeBaseStatus = 'ACTIVE' | 'ARCHIVED';
export type IngestionStatus = 'UPLOADED' | 'PROCESSING' | 'READY' | 'FAILED' | 'OCR_REQUIRED' | 'DELETING' | 'DELETED';

export interface KnowledgeBase {
  id: string;
  owner_id: string;
  name: string;
  description: string | null;
  status: KnowledgeBaseStatus;
  created_at: string;
  updated_at: string;
  document_count: number;
  total_chunks: number;
}

export interface KnowledgeBaseListResponse {
  items: KnowledgeBase[];
  total: number;
  limit: number;
  offset: number;
}

export interface DocumentItem {
  id: string;
  knowledge_base_id: string;
  owner_id: string;
  filename: string;
  original_filename: string;
  content_type: string;
  file_size: number;
  checksum: string;
  storage_key: string;
  status: IngestionStatus;
  ingestion_error: string | null;
  created_at: string;
  updated_at: string;
  chunk_count: number;
  active_version: number;
}

export interface DocumentListResponse {
  items: DocumentItem[];
  total: number;
  limit: number;
  offset: number;
}

export interface DocumentChunk {
  id: string;
  document_id: string;
  document_version_id: string;
  chunk_index: number;
  content: string;
  token_count: number | null;
  character_count: number;
  page_number: number | null;
  section_title: string | null;
  start_offset: number | null;
  end_offset: number | null;
  chunk_metadata: Record<string, unknown>;
  created_at: string;
}

export interface DocumentChunkListResponse {
  items: DocumentChunk[];
  total: number;
  limit: number;
  offset: number;
}

// Phase 12: Knowledge Base Management & Intelligence Types

export interface HealthFinding {
  code: string;
  severity: 'error' | 'warning' | 'info';
  title: string;
  message: string;
  remediation: string;
  is_repairable: boolean;
  affected_entity: string;
}

export interface DocumentHealthReport {
  document_id: string;
  filename: string;
  status: string;
  is_healthy: boolean;
  findings: HealthFinding[];
  chunk_count: number;
  active_version: number;
  embedding_status: string;
  last_indexed_at: string | null;
}

export interface KnowledgeBaseHealthReport {
  knowledge_base_id: string;
  total_documents: number;
  healthy_documents: number;
  unhealthy_documents: number;
  stuck_documents: number;
  total_chunks: number;
  missing_embeddings_count: number;
  findings_summary: Record<string, number>;
  findings: HealthFinding[];
  documents: DocumentHealthReport[];
}

export interface DuplicateCandidate {
  match_type: 'exact_checksum' | 'exact_content' | 'near_duplicate_text';
  similarity_score: number;
  primary_document_id: string;
  primary_filename: string;
  duplicate_document_id: string;
  duplicate_filename: string;
  shared_checksum: string | null;
  storage_impact_bytes: number;
  explanation: string;
}

export interface DuplicateReport {
  knowledge_base_id: string;
  exact_duplicates_count: number;
  near_duplicates_count: number;
  potential_storage_savings_bytes: number;
  candidates: DuplicateCandidate[];
}

export interface CoverageGapItem {
  query: string;
  frequency: number;
  avg_similarity: number | null;
  gap_type: 'insufficient_evidence' | 'empty_retrieval' | 'low_confidence';
  affected_topics: string[];
  suggested_action: string;
}

export interface CoverageReport {
  knowledge_base_id: string;
  total_queries_analyzed: number;
  insufficient_evidence_rate: number;
  unretrieved_documents: Array<{ document_id: string; filename: string }>;
  evidence_gaps: CoverageGapItem[];
  recommendations: string[];
}

export interface ConflictItem {
  topic: string;
  document_a_id: string;
  document_a_name: string;
  document_a_version: number;
  document_a_excerpt: string;
  document_b_id: string;
  document_b_name: string;
  document_b_version: number;
  document_b_excerpt: string;
  conflict_summary: string;
  remediation_guidance: string;
}

export interface ConflictReport {
  knowledge_base_id: string;
  total_conflicts_detected: number;
  items: ConflictItem[];
}

export interface DocumentVersionItem {
  id: string;
  document_id: string;
  version_number: number;
  checksum: string;
  storage_key: string;
  is_active: boolean;
  chunk_count: number;
  created_at: string;
}

export interface DocumentVersionHistoryResponse {
  document_id: string;
  filename: string;
  active_version_number: number;
  total_versions: number;
  is_fresh: boolean;
  versions: DocumentVersionItem[];
}

export interface RepairActionRequest {
  action: 'REPAIR_EMBEDDINGS' | 'REGENERATE_CHUNKS' | 'RETRY_EXTRACTION' | 'RECONCILE_STALE' | 'REINDEX_VERSION';
  dry_run?: boolean;
}

export interface RepairJobResponse {
  job_id: string;
  knowledge_base_id: string;
  document_id: string | null;
  action: string;
  status: 'PENDING' | 'RUNNING' | 'COMPLETED' | 'FAILED';
  dry_run: boolean;
  findings_addressed: string[];
  details: Record<string, unknown> | null;
  error_message: string | null;
  started_at: string;
  completed_at: string | null;
}

