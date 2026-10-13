export type AgentNodeStatus = 'not_connected' | 'idle' | 'running' | 'completed' | 'failed';

export interface WorkflowNodeData {
  id: string;
  name: string;
  type: string;
  status: AgentNodeStatus;
  description: string;
  config: Record<string, string | number | boolean>;
  phase: string;
}
