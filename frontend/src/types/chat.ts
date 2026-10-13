import type { CitationItem } from '@/components/ui/citation-card';
import type { RetrievalLatencyBreakdown } from './search';

export interface WorkflowStepEvent {
  step_id: string;
  name: string;
  status: 'completed' | 'skipped' | 'failed' | 'standby';
  duration_ms: number;
  description?: string;
}

export interface RecoveryMeta {
  recovery_attempted: boolean;
  recovery_count: number;
  failure_category?: string | null;
  recovery_action?: string | null;
  recovery_outcome?: 'recovered' | 'insufficient_evidence' | 'failed' | 'timed_out' | 'permission_denied' | 'exhausted' | string | null;
  rewritten_query?: string | null;
  termination_reason?: string | null;
}

export interface ChatMessage {
  id: string;
  role: 'user' | 'assistant' | 'system';
  content: string;
  timestamp: string;
  citations?: CitationItem[];
  confidence?: number | null;
  verificationStatus?: string;
  isInsufficientEvidence?: boolean;
  answerType?: string;
  answer_type?: string;
  retrievalLatency?: RetrievalLatencyBreakdown;
  generationMs?: number;
  totalMs?: number;
  model?: string;
  tokensUsed?: number | null;
  isStreaming?: boolean;
  retryCount?: number;
  recovery?: RecoveryMeta | null;
  workflowSteps?: WorkflowStepEvent[];
}

export interface SendChatRequest {
  knowledge_base_id: string;
  prompt: string;
  conversation_id?: string;
  mode?: 'hybrid' | 'vector' | 'lexical';
  enable_reranking?: boolean;
  top_k?: number;
}

export interface ChatResponseData {
  id: string;
  role: 'assistant';
  content: string;
  status?: 'answered' | 'recovered' | 'insufficient_evidence' | 'provider_error' | 'retrieval_error' | 'failed' | 'timed_out' | string;
  answer_type?: string;
  answerType?: string;
  timestamp: string;
  knowledge_base_id: string;
  conversation_id?: string | null;
  citations: CitationItem[];
  confidence: number | null;
  verification_status: string;
  is_insufficient_evidence: boolean;
  retrieval_latency: RetrievalLatencyBreakdown | null;
  generation_ms: number;
  total_ms: number;
  model: string;
  tokens_used?: number | null;
  retry_count?: number;
  recovery?: RecoveryMeta | null;
  workflow_steps?: WorkflowStepEvent[];
  collaboration?: CollaborationMeta | null;
}

export interface ResearchSubtask {
  task_id: string;
  title: string;
  query: string;
  dependencies: string[];
  status: 'pending' | 'in_progress' | 'completed' | 'failed' | 'skipped';
  retrieved_chunk_ids: string[];
  findings: string[];
}

export interface TaskPlan {
  plan_id: string;
  is_complex: boolean;
  reasoning: string;
  subtasks: ResearchSubtask[];
  max_execution_steps: number;
}

export interface AgentFinding {
  finding_id: string;
  claim: string;
  evidence_chunk_ids: string[];
  source_titles: string[];
  confidence: number;
  is_contradiction: boolean;
}

export interface VerificationAudit {
  is_verified: boolean;
  supported_claims: string[];
  unsupported_claims: string[];
  citation_validity_ratio: number;
  missing_evidence: string[];
  recommendation: 'proceed' | 'retry_retrieval' | 'abstain' | string;
}

export interface CollaborationMeta {
  mode: string;
  participating_agents: string[];
  plan?: TaskPlan | null;
  findings: AgentFinding[];
  verification?: VerificationAudit | null;
  supervisor_decision: string;
}

export interface Conversation {
  id: string;
  title: string;
  createdAt: string;
  messagesCount: number;
}
