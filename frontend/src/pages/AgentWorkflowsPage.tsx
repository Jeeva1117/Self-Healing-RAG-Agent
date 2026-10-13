import { useState, useMemo, useEffect } from 'react';
import {
  ReactFlow,
  Background,
  Controls,
  MiniMap,
  type Node,
  type Edge,
  Position,
  MarkerType,
} from '@xyflow/react';
import '@xyflow/react/dist/style.css';
import {
  Play,
  RotateCcw,
  Loader2,
  CheckCircle2,
  AlertTriangle,
  Clock,
  Sparkles,
  Database,
  Layers,
  FileText,
  RefreshCw,
  Users,
  ShieldCheck,
  ListOrdered,
  Brain,
  Check,
} from 'lucide-react';
import { Card } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { StatusIndicator } from '@/components/ui/status-indicator';
import { Select } from '@/components/ui/select';
import { Input } from '@/components/ui/input';
import { MarkdownView } from '@/components/ui/markdown-view';
import { CitationCard, type CitationItem } from '@/components/ui/citation-card';
import { useToast } from '@/context/ToastContext';
import { agentService } from '@/services/agentService';
import { knowledgeBaseService } from '@/services/knowledgeBaseService';
import { ApiError } from '@/services/api';
import type { KnowledgeBase } from '@/types/knowledgeBase';
import type { ChatResponseData, WorkflowStepEvent } from '@/types/chat';

interface NodeDetailsData {
  id: string;
  name: string;
  type: string;
  phase: string;
  description: string;
  config: Record<string, string | number | boolean>;
}

const NODE_DEFINITIONS: Record<string, NodeDetailsData> = {
  '1': {
    id: '1',
    name: 'Query Understanding',
    type: 'Agent 1 — Query Understanding Agent',
    phase: 'Intent & Query',
    description: 'Analyzes user question, strips conversational noise, identifies intent and entities, evaluates ambiguity, and decides retrieval strategy.',
    config: {
      strategy: 'intent_and_entity_analysis',
      ambiguity_guard: true,
      extract_retrieval_needs: true,
    },
  },
  '2': {
    id: '2',
    name: 'Planning Agent',
    type: 'Agent 2 — Task Planning Agent',
    phase: 'Decomposition',
    description: 'Decomposes complex research questions into bounded, dependency-ordered subtasks with execution limits.',
    config: {
      max_subtasks: 3,
      max_execution_steps: 6,
      subtask_dependency_resolution: true,
    },
  },
  '3': {
    id: '3',
    name: 'Retrieval Agent',
    type: 'Agent 3 — Specialized Retrieval Agent',
    phase: 'Hybrid Retrieval',
    description: 'Executes subtask-aware hybrid retrieval (dense vector similarity + BM25 keyword fusion with RRF and reranking).',
    config: {
      retrieval_mode: 'subtask_aware_hybrid',
      top_k_per_task: 5,
      rrf_k: 60,
    },
  },
  '4': {
    id: '4',
    name: 'Evidence Analysis',
    type: 'Agent 4 — Research & Evidence Analysis Agent',
    phase: 'Evidence Synthesis',
    description: 'Synthesizes facts across retrieved chunks, extracts verified factual claims with document provenance, and detects contradictions.',
    config: {
      claim_to_source_mapping: true,
      contradiction_detection: true,
      confidence_scoring: true,
    },
  },
  '5': {
    id: '5',
    name: 'Response Generation',
    type: 'Agent 6 — Grounded Response Generation Agent',
    phase: 'Grounded Output',
    description: 'Synthesizes grounded answers strictly from verified evidence findings with real sentence-level source citations.',
    config: {
      synthesis_mode: 'evidence_findings_grounded',
      strict_provenance: true,
      temperature: 0.2,
    },
  },
  '6': {
    id: '6',
    name: 'Citation Validator',
    type: 'Provenance Auditing Agent',
    phase: 'Provenance Audit',
    description: 'Audits citation tags against retrieved chunks and removes ungrounded references.',
    config: {
      strict_provenance: true,
      strip_hallucinated_citations: true,
    },
  },
  '9': {
    id: '9',
    name: 'Verification Agent',
    type: 'Agent 5 — Verification & Factuality Agent',
    phase: 'Fact Verification',
    description: 'Audits answer claims against retrieved evidence, verifies citation validity, and recommends proceed, retry, or abstain.',
    config: {
      factuality_audit: true,
      citation_validity_threshold: 0.75,
      abstain_on_insufficient: true,
    },
  },
  '7': {
    id: '7',
    name: 'Workflow Supervisor',
    type: 'Agent 7 — Workflow Supervisor / Coordinator',
    phase: 'Supervision & State',
    description: 'Coordinates multi-agent workflow state, enforces bounded execution cycles, routes retry loops, and prevents infinite delegation.',
    config: {
      max_workflow_cycles: 2,
      cycle_prevention: true,
      telemetry_recording: true,
    },
  },
  '8': {
    id: '8',
    name: 'Self-Healing Recovery',
    type: 'Adaptive Recovery Engine',
    phase: 'Adaptive Recovery',
    description: 'Diagnoses failure category, selects bounded allowlisted recovery action, and safeguards loop.',
    config: {
      max_retries: 2,
      cycle_detection: true,
      timeout_seconds: 45,
      adaptation_strategy: 'adaptive_policy_allowlist',
    },
  },
};

const STEP_TO_NODE_ID: Record<string, string> = {
  query_analysis: '1',
  query_understanding: '1',
  scope_authorization: '1',
  retrieval_strategy: '2',
  planning: '2',
  retrieval: '3',
  retrieval_agent: '3',
  evidence_assessment: '4',
  evidence_analysis: '4',
  bounded_retry: '8',
  grounded_generation: '5',
  response_generation: '5',
  citation_validation: '6',
  answer_verification: '9',
  verification_agent: '9',
  finalization: '7',
  supervisor: '7',
};

export function AgentWorkflowsPage() {
  const { toast } = useToast();
  const [selectedNodeId, setSelectedNodeId] = useState<string>('3');

  // Knowledge bases state
  const [knowledgeBases, setKnowledgeBases] = useState<KnowledgeBase[]>([]);
  const [selectedKbId, setSelectedKbId] = useState<string>('');
  const [loadingKbs, setLoadingKbs] = useState<boolean>(true);

  // Workflow run input state
  const [testPrompt, setTestPrompt] = useState<string>('What are the core concepts covered in this knowledge base?');
  const [isExecuting, setIsExecuting] = useState<boolean>(false);
  const [orchestrationMode, setOrchestrationMode] = useState<'collaborative' | 'single'>('collaborative');

  // Workflow execution result state
  const [executionResult, setExecutionResult] = useState<ChatResponseData | null>(null);
  const [executionError, setExecutionError] = useState<{ code: string; message: string; details?: unknown } | null>(null);

  // Load knowledge bases on mount
  useEffect(() => {
    async function fetchKbs() {
      setLoadingKbs(true);
      try {
        const resp = await knowledgeBaseService.listKnowledgeBases(0, 50);
        const items = resp.items || [];
        setKnowledgeBases(items);
        if (items.length > 0) {
          const pythonKb = items.find((k) => k.name.toLowerCase().includes('python'));
          setSelectedKbId(pythonKb ? pythonKb.id : items[0].id);
        }
      } catch (err) {
        console.error('Failed to fetch knowledge bases', err);
      } finally {
        setLoadingKbs(false);
      }
    }
    fetchKbs();
  }, []);

  // Pre-configured node definition
  const selectedNode = NODE_DEFINITIONS[selectedNodeId] || NODE_DEFINITIONS['3'];

  // Map of executed step telemetry per node
  const nodeExecutionMap = useMemo(() => {
    if (!executionResult?.workflow_steps) return {};
    const map: Record<string, WorkflowStepEvent> = {};
    for (const step of executionResult.workflow_steps) {
      const nodeId = STEP_TO_NODE_ID[step.step_id];
      if (nodeId) {
        map[nodeId] = step;
      }
    }
    return map;
  }, [executionResult]);

  // Dynamic React Flow Nodes based on live execution telemetry
  const initialNodes: Node[] = useMemo(() => {
    const getNodeStyle = (id: string, isRecovery = false) => {
      const step = nodeExecutionMap[id];
      const isSelected = selectedNodeId === id;

      if (step) {
        if (step.status === 'failed') {
          return {
            background: '#FEF2F2',
            color: '#991B1B',
            border: isSelected ? '3px solid #DC2626' : '2px solid #EF4444',
            borderRadius: '12px',
            padding: '12px 18px',
            fontSize: '12px',
            fontWeight: '700',
            boxShadow: '0 2px 8px 0 rgba(239, 68, 68, 0.25)',
          };
        }
        if (isRecovery) {
          return {
            background: '#FFFBEB',
            color: '#B45309',
            border: isSelected ? '3px solid #D97706' : '2px solid #F59E0B',
            borderRadius: '12px',
            padding: '12px 18px',
            fontSize: '12px',
            fontWeight: '700',
            boxShadow: '0 2px 8px 0 rgba(245, 158, 11, 0.25)',
          };
        }
        return {
          background: '#F0FDF4',
          color: '#166534',
          border: isSelected ? '3px solid #16A34A' : '2px solid #22C55E',
          borderRadius: '12px',
          padding: '12px 18px',
          fontSize: '12px',
          fontWeight: '700',
          boxShadow: '0 2px 8px 0 rgba(34, 197, 94, 0.25)',
        };
      }

      if (isRecovery) {
        return {
          background: '#FEF2F2',
          color: '#B91C1C',
          border: isSelected ? '3px solid #B91C1C' : '2px solid #DC2626',
          borderRadius: '12px',
          padding: '12px 18px',
          fontSize: '12px',
          fontWeight: '700',
          boxShadow: '0 2px 6px 0 rgba(220, 38, 38, 0.15)',
        };
      }

      return {
        background: isSelected ? '#EFF6FF' : '#FFFFFF',
        color: isSelected ? '#1D4ED8' : '#0F172A',
        border: isSelected ? '3px solid #1D4ED8' : '2px solid #2563EB',
        borderRadius: '12px',
        padding: '12px 18px',
        fontSize: '12px',
        fontWeight: '700',
        boxShadow: isSelected ? '0 2px 6px 0 rgba(37, 99, 235, 0.2)' : '0 2px 4px 0 rgba(0, 0, 0, 0.06)',
      };
    };

    const getLabel = (id: string, defaultName: string) => {
      const step = nodeExecutionMap[id];
      if (step) {
        return `${defaultName} (${step.duration_ms.toFixed(0)}ms)`;
      }
      return defaultName;
    };

    return [
      {
        id: '1',
        data: { label: getLabel('1', 'Query Analysis') },
        position: { x: 20, y: 80 },
        sourcePosition: Position.Right,
        style: getNodeStyle('1'),
      },
      {
        id: '2',
        data: { label: getLabel('2', 'Planner') },
        position: { x: 195, y: 80 },
        sourcePosition: Position.Right,
        targetPosition: Position.Left,
        style: getNodeStyle('2'),
      },
      {
        id: '3',
        data: { label: getLabel('3', 'Hybrid Retriever') },
        position: { x: 375, y: 80 },
        sourcePosition: Position.Right,
        targetPosition: Position.Left,
        style: getNodeStyle('3'),
      },
      {
        id: '4',
        data: { label: getLabel('4', 'Evidence Check') },
        position: { x: 575, y: 80 },
        sourcePosition: Position.Right,
        targetPosition: Position.Left,
        style: getNodeStyle('4'),
      },
      {
        id: '5',
        data: { label: getLabel('5', 'Generator') },
        position: { x: 760, y: 80 },
        sourcePosition: Position.Bottom,
        targetPosition: Position.Left,
        style: getNodeStyle('5'),
      },
      {
        id: '6',
        data: { label: getLabel('6', 'Citations') },
        position: { x: 760, y: 220 },
        sourcePosition: Position.Left,
        targetPosition: Position.Top,
        style: getNodeStyle('6'),
      },
      {
        id: '9',
        data: { label: getLabel('9', 'Verifier') },
        position: { x: 575, y: 220 },
        sourcePosition: Position.Left,
        targetPosition: Position.Right,
        style: getNodeStyle('9'),
      },
      {
        id: '7',
        data: { label: getLabel('7', 'Finalization') },
        position: { x: 400, y: 220 },
        sourcePosition: Position.Left,
        targetPosition: Position.Right,
        style: getNodeStyle('7'),
      },
      {
        id: '8',
        data: {
          label:
            nodeExecutionMap['8']
              ? `Recovery (Retried ${nodeExecutionMap['8'].duration_ms.toFixed(0)}ms)`
              : 'Recovery Loop',
        },
        position: { x: 210, y: 220 },
        sourcePosition: Position.Top,
        targetPosition: Position.Right,
        style: getNodeStyle('8', true),
      },
    ];
  }, [nodeExecutionMap, selectedNodeId]);

  // Edges highlighting self-healing loop
  const initialEdges: Edge[] = useMemo(() => {
    const isRetryActive = Boolean(nodeExecutionMap['8']);

    return [
      { id: 'e1-2', source: '1', target: '2', animated: true, style: { stroke: '#2563EB', strokeWidth: 2 } },
      { id: 'e2-3', source: '2', target: '3', animated: true, style: { stroke: '#2563EB', strokeWidth: 2 } },
      { id: 'e3-4', source: '3', target: '4', animated: true, style: { stroke: '#2563EB', strokeWidth: 2 } },
      { id: 'e4-5', source: '4', target: '5', animated: true, style: { stroke: '#2563EB', strokeWidth: 2 } },
      { id: 'e5-6', source: '5', target: '6', animated: true, style: { stroke: '#2563EB', strokeWidth: 2 } },
      { id: 'e6-9', source: '6', target: '9', animated: true, style: { stroke: '#2563EB', strokeWidth: 2 } },
      { id: 'e9-7', source: '9', target: '7', animated: true, style: { stroke: '#2563EB', strokeWidth: 2 } },
      {
        id: 'e4-8',
        source: '4',
        target: '8',
        animated: isRetryActive,
        label: isRetryActive ? 'Insufficient Evidence ⚠️' : 'Insufficient Evidence',
        labelStyle: { fill: '#DC2626', fontSize: 10, fontWeight: 600 },
        style: { stroke: '#DC2626', strokeDasharray: '4 4', strokeWidth: isRetryActive ? 3 : 1.5 },
      },
      {
        id: 'e8-3',
        source: '8',
        target: '3',
        animated: isRetryActive,
        label: isRetryActive ? 'Active Bounded Retry (35 chunks)' : 'Self-Healing Retry Loop',
        labelStyle: { fill: '#DC2626', fontSize: 10, fontWeight: 600 },
        markerEnd: { type: MarkerType.ArrowClosed, color: '#DC2626' },
        style: { stroke: '#DC2626', strokeWidth: isRetryActive ? 3 : 2 },
      },
      {
        id: 'e9-8',
        source: '9',
        target: '8',
        animated: isRetryActive,
        label: 'Verification Recovery',
        labelStyle: { fill: '#D97706', fontSize: 10, fontWeight: 600 },
        style: { stroke: '#D97706', strokeDasharray: '4 4', strokeWidth: 1.5 },
      },
    ];
  }, [nodeExecutionMap]);

  const handleNodeClick = (_: React.MouseEvent, node: Node) => {
    setSelectedNodeId(node.id);
  };

  // Real backend workflow execution
  const handleSimulateGraphRun = async () => {
    if (!selectedKbId) {
      toast.error('Please select an authorized Knowledge Base first');
      return;
    }

    if (!testPrompt.trim()) {
      toast.error('Please enter a query or prompt for the workflow simulation');
      return;
    }

    setIsExecuting(true);
    setExecutionError(null);

    try {
      const payload = {
        knowledge_base_id: selectedKbId,
        prompt: testPrompt.trim(),
        top_k: 5,
        enable_reranking: true,
      };

      const data = orchestrationMode === 'collaborative'
        ? await agentService.collaborateWorkflow(payload)
        : await agentService.simulateWorkflow(payload);

      setExecutionResult(data);

      if (data.status === 'answered' || data.status === 'recovered') {
        const collabNote = data.collaboration ? ` (7-Agent Collaboration)` : '';
        toast.success(`Workflow completed: Answered with ${data.citations?.length || 0} citations${collabNote}`);
      } else if (data.status === 'insufficient_evidence') {
        toast.info('Workflow completed: Insufficient evidence in knowledge base (Supervisor guided resolution)');
      } else {
        toast.warning(`Workflow finished with status: ${data.status}`);
      }
    } catch (err) {
      if (err instanceof ApiError) {
        setExecutionError({
          code: err.code,
          message: err.message,
          details: err.details,
        });
        toast.error(`Workflow execution failed: ${err.message}`);
      } else {
        const errorMsg = err instanceof Error ? err.message : 'Unknown execution failure';
        setExecutionError({
          code: 'EXECUTION_FAILED',
          message: errorMsg,
        });
        toast.error(`Execution failed: ${errorMsg}`);
      }
    } finally {
      setIsExecuting(false);
    }
  };

  const handleResetView = () => {
    setExecutionResult(null);
    setExecutionError(null);
    toast.info('Workflow execution state reset');
  };

  return (
    <div className="space-y-6">
      {/* Top Header */}
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-slate-900 dark:text-white">
            Agent Workflows & Self-Healing Loop
          </h1>
          <p className="text-xs sm:text-sm text-slate-500 dark:text-slate-400 mt-1">
            Visual LangGraph orchestration graph. Execute real state graphs to inspect live node transitions, evidence assessment, and self-healing recovery.
          </p>
        </div>

        <div className="flex items-center gap-2">
          <Button
            variant="outline"
            size="sm"
            onClick={handleResetView}
            className="gap-1.5 text-xs bg-white text-slate-700 border-slate-200 dark:bg-slate-900 dark:border-slate-800 dark:text-slate-200"
          >
            <RotateCcw className="h-3.5 w-3.5" />
            <span>Reset View</span>
          </Button>

          <Button
            size="sm"
            disabled={isExecuting || loadingKbs || knowledgeBases.length === 0}
            onClick={handleSimulateGraphRun}
            className="gap-1.5 text-xs bg-blue-600 hover:bg-blue-700 text-white font-medium shadow-sm transition-all disabled:opacity-50"
          >
            {isExecuting ? (
              <>
                <Loader2 className="h-3.5 w-3.5 animate-spin" />
                <span>Running Workflow...</span>
              </>
            ) : (
              <>
                <Play className="h-3.5 w-3.5" />
                <span>{orchestrationMode === 'collaborative' ? 'Run Multi-Agent Collaboration' : 'Simulate Graph Run'}</span>
              </>
            )}
          </Button>
        </div>
      </div>

      {/* Simulation Setup Control Bar */}
      <Card className="p-4 border-slate-200 bg-white shadow-2xs rounded-2xl dark:bg-slate-900 dark:border-slate-800">
        <div className="flex flex-col md:flex-row gap-4 items-stretch md:items-center justify-between">
          {/* Architecture Mode Selector */}
          <div className="flex flex-col gap-1 md:w-1/4">
            <label className="text-[11px] font-semibold text-slate-500 dark:text-slate-400 uppercase tracking-wider flex items-center gap-1.5">
              <Users className="h-3 w-3 text-blue-600" />
              <span>Architecture Mode</span>
            </label>
            <Select
              value={orchestrationMode}
              onChange={(e) => setOrchestrationMode(e.target.value as 'collaborative' | 'single')}
              className="text-xs font-medium"
            >
              <option value="collaborative">Multi-Agent Collaboration Engine</option>
              <option value="single">Single-Agent Graph Execution</option>
            </Select>
          </div>

          {/* KB Selector */}
          <div className="flex flex-col gap-1 md:w-1/4">
            <label className="text-[11px] font-semibold text-slate-500 dark:text-slate-400 uppercase tracking-wider flex items-center gap-1.5">
              <Database className="h-3 w-3 text-blue-600" />
              <span>Target Knowledge Base</span>
            </label>
            {loadingKbs ? (
              <div className="h-9 rounded-lg bg-slate-100 animate-pulse dark:bg-slate-800" />
            ) : knowledgeBases.length === 0 ? (
              <div className="text-xs text-amber-600 dark:text-amber-400 py-1.5">
                No Knowledge Bases found. Create one first to execute graph.
              </div>
            ) : (
              <Select
                value={selectedKbId}
                onChange={(e) => setSelectedKbId(e.target.value)}
                className="text-xs font-medium"
              >
                {knowledgeBases.map((kb) => (
                  <option key={kb.id} value={kb.id}>
                    {kb.name} ({kb.document_count || 0} docs)
                  </option>
                ))}
              </Select>
            )}
          </div>

          {/* Prompt Input */}
          <div className="flex flex-col gap-1 flex-1">
            <div className="flex items-center justify-between">
              <label className="text-[11px] font-semibold text-slate-500 dark:text-slate-400 uppercase tracking-wider flex items-center gap-1.5">
                <Sparkles className="h-3 w-3 text-blue-600" />
                <span>Test Query / Evaluation Prompt</span>
              </label>
              <div className="flex items-center gap-2">
                <button
                  type="button"
                  onClick={() => setTestPrompt('What are operators in Python?')}
                  className="text-[10px] text-blue-600 hover:underline dark:text-blue-400"
                >
                  Grounded Example
                </button>
                <span className="text-slate-300 dark:text-slate-700">|</span>
                <button
                  type="button"
                  onClick={() => setTestPrompt('Explain quantum entanglement in interstellar deep space wormholes')}
                  className="text-[10px] text-amber-600 hover:underline dark:text-amber-400"
                >
                  Trigger Self-Healing
                </button>
              </div>
            </div>
            <Input
              value={testPrompt}
              onChange={(e) => setTestPrompt(e.target.value)}
              placeholder="Enter question to run through the LangGraph workflow..."
              className="text-xs"
              disabled={isExecuting}
              onKeyDown={(e) => {
                if (e.key === 'Enter' && !isExecuting) {
                  handleSimulateGraphRun();
                }
              }}
            />
          </div>
        </div>
      </Card>

      {/* Main Graph & Inspector Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Canvas: React Flow */}
        <div className="lg:col-span-2 h-[560px] rounded-2xl border border-slate-200 bg-white overflow-hidden shadow-sm relative dark:bg-slate-900 dark:border-slate-800">
          <ReactFlow
            nodes={initialNodes}
            edges={initialEdges}
            onNodeClick={handleNodeClick}
            fitView
            minZoom={0.5}
            maxZoom={1.5}
          >
            <Background color="#E2E8F0" gap={18} size={1} />
            <Controls className="bg-white border-slate-200 rounded-lg shadow-sm" />
            <MiniMap
              nodeColor={(n) => (n.id === '8' ? '#DC2626' : '#2563EB')}
              className="bg-white border-slate-200 rounded-lg"
            />
          </ReactFlow>

          <div className="absolute top-3 left-3 bg-white/90 backdrop-blur-xs px-3 py-1.5 rounded-lg border border-slate-200 text-[11px] text-slate-600 shadow-2xs dark:bg-slate-900/90 dark:border-slate-800 dark:text-slate-400">
            {executionResult ? (
              <span className="flex items-center gap-1.5 text-emerald-700 dark:text-emerald-400 font-semibold">
                <CheckCircle2 className="h-3.5 w-3.5" />
                Live Telemetry Rendered — Click any executed node to inspect
              </span>
            ) : (
              'Click any node to view configuration parameters and live telemetry'
            )}
          </div>
        </div>

        {/* Node Detail Panel */}
        <Card className="p-5 flex flex-col justify-between border-slate-200 bg-white shadow-sm rounded-2xl dark:bg-slate-900 dark:border-slate-800">
          <div className="space-y-4">
            <div className="flex items-center justify-between pb-3 border-b border-slate-100 dark:border-slate-800">
              <div className="flex items-center gap-2">
                <StatusIndicator
                  status={
                    nodeExecutionMap[selectedNode.id]?.status === 'failed'
                      ? 'disconnected'
                      : 'operational'
                  }
                />
                <h3 className="font-bold text-sm text-slate-900 dark:text-slate-100">{selectedNode.name}</h3>
              </div>
              <Badge variant="outline" size="sm" className="bg-blue-50 text-blue-700 border-blue-200 font-mono text-[10px]">
                {selectedNode.phase}
              </Badge>
            </div>

            {/* Live Telemetry If Executed */}
            {nodeExecutionMap[selectedNode.id] && (
              <div className="p-3 rounded-xl border border-emerald-200 bg-emerald-50/60 dark:bg-emerald-950/20 dark:border-emerald-900/60 space-y-1.5">
                <div className="flex items-center justify-between">
                  <span className="text-[10px] font-bold text-emerald-800 dark:text-emerald-300 uppercase tracking-wider flex items-center gap-1">
                    <Clock className="h-3 w-3" />
                    <span>Live Node Telemetry</span>
                  </span>
                  <Badge
                    size="sm"
                    className="bg-emerald-600 text-white font-mono text-[10px]"
                  >
                    {nodeExecutionMap[selectedNode.id].duration_ms.toFixed(1)} ms
                  </Badge>
                </div>
                <p className="text-xs text-emerald-900 dark:text-emerald-200 font-medium leading-relaxed">
                  {nodeExecutionMap[selectedNode.id].description || 'Executed successfully'}
                </p>
              </div>
            )}

            <div className="space-y-1">
              <span className="text-[11px] font-semibold text-slate-400 uppercase tracking-wider">
                Agent Classification
              </span>
              <p className="text-xs font-medium text-slate-700 dark:text-slate-300">{selectedNode.type}</p>
            </div>

            <div className="space-y-1">
              <span className="text-[11px] font-semibold text-slate-400 uppercase tracking-wider">
                Role & Objective
              </span>
              <p className="text-xs text-slate-600 dark:text-slate-400 leading-relaxed">{selectedNode.description}</p>
            </div>

            <div className="space-y-2 pt-2 border-t border-slate-100 dark:border-slate-800">
              <span className="text-[11px] font-semibold text-slate-400 uppercase tracking-wider block">
                Runtime Hyperparameters
              </span>

              <div className="rounded-xl border border-slate-200 bg-slate-50 p-3 space-y-2 text-xs font-mono dark:bg-slate-800/50 dark:border-slate-800">
                {Object.entries(selectedNode.config).map(([key, val]) => (
                  <div key={key} className="flex items-center justify-between">
                    <span className="text-slate-500">{key}:</span>
                    <span className="text-blue-700 dark:text-blue-300 font-semibold">{String(val)}</span>
                  </div>
                ))}
              </div>
            </div>
          </div>

          <div className="pt-4 border-t border-slate-100 dark:border-slate-800 text-[11px] text-slate-500">
            {executionResult ? (
              <span className="text-emerald-600 dark:text-emerald-400 font-medium">
                Active LangGraph telemetry synchronized from backend execution.
              </span>
            ) : (
              'Click "Simulate Graph Run" to trigger real LangGraph execution.'
            )}
          </div>
        </Card>
      </div>

      {/* Execution Error Banner (Requirement 7) */}
      {executionError && (
        <Card className="p-5 border-red-200 bg-red-50/70 dark:bg-red-950/20 dark:border-red-900/60 rounded-2xl shadow-sm">
          <div className="flex items-start gap-4">
            <div className="p-2.5 bg-red-100 text-red-600 rounded-xl dark:bg-red-900/40 dark:text-red-400 shrink-0">
              <AlertTriangle className="h-5 w-5" />
            </div>
            <div className="space-y-1">
              <div className="flex items-center gap-2">
                <h3 className="text-sm font-bold text-red-900 dark:text-red-200">
                  LangGraph Workflow Execution Failed
                </h3>
                <Badge variant="outline" className="bg-red-100 text-red-800 border-red-300 font-mono text-[10px]">
                  {executionError.code}
                </Badge>
              </div>
              <p className="text-xs text-red-700 dark:text-red-300 leading-relaxed">
                {executionError.message}
              </p>
            </div>
          </div>
        </Card>
      )}

      {/* Execution Results & Real Provenance (Requirement 6) */}
      {executionResult && (
        <div className="space-y-6 pt-2">
          {/* Executive Metrics Bar */}
          <Card className="p-4 border-slate-200 bg-white rounded-2xl shadow-sm dark:bg-slate-900 dark:border-slate-800">
            <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-4 text-center divide-y sm:divide-y-0 sm:divide-x divide-slate-100 dark:divide-slate-800">
              <div className="flex flex-col items-center justify-center p-2">
                <span className="text-[10px] font-semibold text-slate-400 uppercase tracking-wider">Status</span>
                <Badge
                  className={`mt-1 font-semibold text-[11px] ${
                    executionResult.status === 'answered'
                      ? 'bg-emerald-100 text-emerald-800 dark:bg-emerald-900/40 dark:text-emerald-300'
                      : executionResult.status === 'recovered'
                      ? 'bg-purple-100 text-purple-800 dark:bg-purple-900/40 dark:text-purple-300'
                      : executionResult.status === 'insufficient_evidence'
                      ? 'bg-amber-100 text-amber-800 dark:bg-amber-900/40 dark:text-amber-300'
                      : 'bg-red-100 text-red-800 dark:bg-red-900/40 dark:text-red-300'
                  }`}
                >
                  {executionResult.status}
                </Badge>
              </div>

              <div className="flex flex-col items-center justify-center p-2">
                <span className="text-[10px] font-semibold text-slate-400 uppercase tracking-wider">Total Latency</span>
                <span className="text-base font-bold text-slate-900 dark:text-slate-100 mt-0.5">
                  {executionResult.total_ms?.toFixed(1) || '0'} ms
                </span>
              </div>

              <div className="flex flex-col items-center justify-center p-2">
                <span className="text-[10px] font-semibold text-slate-400 uppercase tracking-wider">Retrieval Time</span>
                <span className="text-base font-bold text-slate-900 dark:text-slate-100 mt-0.5">
                  {executionResult.retrieval_latency?.total_ms?.toFixed(1) || '0'} ms
                </span>
              </div>

              <div className="flex flex-col items-center justify-center p-2">
                <span className="text-[10px] font-semibold text-slate-400 uppercase tracking-wider">Synthesis Time</span>
                <span className="text-base font-bold text-slate-900 dark:text-slate-100 mt-0.5">
                  {executionResult.generation_ms?.toFixed(1) || '0'} ms
                </span>
              </div>

              <div className="flex flex-col items-center justify-center p-2">
                <span className="text-[10px] font-semibold text-slate-400 uppercase tracking-wider">Citations</span>
                <span className="text-base font-bold text-blue-600 dark:text-blue-400 mt-0.5">
                  {executionResult.citations?.length || 0} Sources
                </span>
              </div>

              <div className="flex flex-col items-center justify-center p-2">
                <span className="text-[10px] font-semibold text-slate-400 uppercase tracking-wider">Self-Healing Retries</span>
                <span
                  className={`text-base font-bold mt-0.5 ${
                    (executionResult.retry_count || 0) > 0
                      ? 'text-amber-600 dark:text-amber-400'
                      : 'text-slate-900 dark:text-slate-100'
                  }`}
                >
                  {executionResult.retry_count || 0}
                </span>
              </div>
            </div>
          </Card>

          {/* Phase 8 Self-Healing Recovery Engine Telemetry Panel */}
          {((executionResult.recovery && executionResult.recovery.recovery_attempted) || (executionResult.retry_count || 0) > 0) && (
            <Card className="p-4 border-amber-200 bg-amber-50/60 dark:bg-amber-950/20 dark:border-amber-900/60 rounded-2xl shadow-2xs">
              <div className="flex items-start justify-between flex-wrap gap-4">
                <div className="space-y-1">
                  <div className="flex items-center gap-2">
                    <div className="p-1.5 bg-amber-100 text-amber-700 rounded-lg dark:bg-amber-900/40 dark:text-amber-300">
                      <RotateCcw className="h-4 w-4" />
                    </div>
                    <h4 className="text-xs font-bold text-amber-900 dark:text-amber-200 uppercase tracking-wider">
                      Self-Healing Recovery Telemetry
                    </h4>
                    <Badge variant="outline" size="sm" className="bg-amber-100 text-amber-800 border-amber-300 font-mono text-[10px]">
                      Outcome: {executionResult.recovery?.recovery_outcome || (executionResult.status === 'recovered' ? 'recovered' : 'insufficient_evidence')}
                    </Badge>
                  </div>
                  <p className="text-xs text-amber-900/80 dark:text-amber-200/80 leading-relaxed font-medium">
                    {executionResult.recovery?.termination_reason || `Triggered adaptive recovery action: ${executionResult.recovery?.recovery_action || 'bounded retrieval expansion'}`}
                  </p>
                </div>

                <div className="flex items-center gap-4 text-xs font-mono">
                  {executionResult.recovery?.failure_category && (
                    <div className="px-2.5 py-1 rounded-lg bg-white/80 dark:bg-slate-900/80 border border-amber-200 dark:border-amber-800">
                      <span className="text-slate-400 text-[10px] block uppercase">Failure Category</span>
                      <span className="font-semibold text-amber-800 dark:text-amber-300">{executionResult.recovery.failure_category}</span>
                    </div>
                  )}
                  {executionResult.recovery?.recovery_action && (
                    <div className="px-2.5 py-1 rounded-lg bg-white/80 dark:bg-slate-900/80 border border-amber-200 dark:border-amber-800">
                      <span className="text-slate-400 text-[10px] block uppercase">Action Taken</span>
                      <span className="font-semibold text-amber-800 dark:text-amber-300">{executionResult.recovery.recovery_action}</span>
                    </div>
                  )}
                  <div className="px-2.5 py-1 rounded-lg bg-white/80 dark:bg-slate-900/80 border border-amber-200 dark:border-amber-800">
                    <span className="text-slate-400 text-[10px] block uppercase">Verification Status</span>
                    <span className="font-semibold text-slate-800 dark:text-slate-200">{executionResult.verification_status}</span>
                  </div>
                </div>
              </div>

              {executionResult.recovery?.rewritten_query && (
                <div className="mt-2.5 pt-2 border-t border-amber-200/60 dark:border-amber-900/60 text-xs flex items-center gap-2">
                  <span className="text-amber-700 dark:text-amber-400 font-semibold text-[11px]">Rewritten Intent Query:</span>
                  <code className="bg-white/90 dark:bg-slate-900/90 px-2 py-0.5 rounded text-[11px] text-amber-900 dark:text-amber-200 font-mono border border-amber-200 dark:border-amber-800">
                    {executionResult.recovery.rewritten_query}
                  </code>
                </div>
              )}
            </Card>
          )}

          {/* Multi-Agent Collaboration Telemetry Panel */}
          {executionResult.collaboration && (
            <Card className="p-5 border-blue-200 bg-blue-50/40 dark:bg-blue-950/20 dark:border-blue-900/60 rounded-2xl shadow-sm space-y-5">
              {/* Header */}
              <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 pb-3 border-b border-blue-100 dark:border-blue-900/40">
                <div className="flex items-center gap-2.5">
                  <div className="p-2 bg-blue-600 text-white rounded-xl shadow-xs">
                    <Users className="h-4 w-4" />
                  </div>
                  <div>
                    <div className="flex items-center gap-2">
                      <h4 className="text-sm font-bold text-slate-900 dark:text-slate-100">
                        Multi-Agent Collaboration Architecture
                      </h4>
                      <Badge variant="outline" size="sm" className="bg-blue-100 text-blue-800 border-blue-300 font-mono text-[10px]">
                        Collaboration Active
                      </Badge>
                    </div>
                    <p className="text-xs text-slate-500 dark:text-slate-400 mt-0.5">
                      {executionResult.collaboration.participating_agents.length} specialized agents coordinated via shared typed LangGraph state
                    </p>
                  </div>
                </div>

                <div className="flex items-center gap-2">
                  <span className="text-[11px] font-semibold text-slate-500 uppercase tracking-wider">Supervisor Status:</span>
                  <Badge
                    size="sm"
                    className={`font-semibold text-xs ${
                      executionResult.collaboration.supervisor_decision === 'approved'
                        ? 'bg-emerald-600 text-white'
                        : executionResult.collaboration.supervisor_decision === 'recovered'
                        ? 'bg-purple-600 text-white'
                        : 'bg-amber-600 text-white'
                    }`}
                  >
                    {executionResult.collaboration.supervisor_decision.toUpperCase()}
                  </Badge>
                </div>
              </div>

              {/* Participating Agents Badges */}
              <div className="flex flex-wrap gap-1.5 items-center">
                <span className="text-[10px] font-bold text-slate-400 uppercase tracking-wider mr-1">Coordinated Agents:</span>
                {executionResult.collaboration.participating_agents.map((agentName, idx) => (
                  <Badge
                    key={idx}
                    variant="outline"
                    className="text-[10px] bg-white text-slate-700 border-slate-200 dark:bg-slate-900 dark:text-slate-300 dark:border-slate-800 flex items-center gap-1"
                  >
                    <Check className="h-2.5 w-2.5 text-emerald-600" />
                    <span>{agentName}</span>
                  </Badge>
                ))}
              </div>

              {/* Sub-panels Grid */}
              <div className="grid grid-cols-1 md:grid-cols-3 gap-4 pt-1">
                {/* Panel 1: Agent 2 Planning & Subtasks */}
                <div className="p-3.5 rounded-xl bg-white border border-slate-200 dark:bg-slate-900 dark:border-slate-800 space-y-2.5 shadow-2xs">
                  <div className="flex items-center justify-between pb-2 border-b border-slate-100 dark:border-slate-800">
                    <span className="text-xs font-bold text-slate-800 dark:text-slate-200 flex items-center gap-1.5">
                      <ListOrdered className="h-3.5 w-3.5 text-blue-600" />
                      <span>Agent 2: Research Plan</span>
                    </span>
                    <Badge size="sm" variant="outline" className="text-[10px] font-mono">
                      {executionResult.collaboration.plan?.subtasks?.length || 0} subtasks
                    </Badge>
                  </div>

                  <p className="text-[11px] text-slate-600 dark:text-slate-400 leading-relaxed font-medium">
                    {executionResult.collaboration.plan?.reasoning || 'Standard single-phase research execution.'}
                  </p>

                  <div className="space-y-1.5 max-h-48 overflow-y-auto pr-1">
                    {executionResult.collaboration.plan?.subtasks?.map((subtask) => (
                      <div
                        key={subtask.task_id}
                        className="p-2 rounded-lg bg-slate-50 dark:bg-slate-800/60 border border-slate-100 dark:border-slate-800 text-[11px] space-y-1"
                      >
                        <div className="flex items-center justify-between">
                          <span className="font-semibold text-slate-800 dark:text-slate-200">{subtask.title}</span>
                          <Badge
                            size="sm"
                            className={`text-[9px] px-1.5 py-0 ${
                              subtask.status === 'completed'
                                ? 'bg-emerald-100 text-emerald-800 dark:bg-emerald-900/50 dark:text-emerald-300'
                                : 'bg-slate-100 text-slate-800'
                            }`}
                          >
                            {subtask.status}
                          </Badge>
                        </div>
                        <div className="text-[10px] text-slate-500 font-mono truncate">
                          Query: {subtask.query}
                        </div>
                        {subtask.findings?.length > 0 && (
                          <div className="text-[10px] text-emerald-700 dark:text-emerald-400 font-medium">
                            ✓ {subtask.findings.length} findings extracted
                          </div>
                        )}
                      </div>
                    ))}
                  </div>
                </div>

                {/* Panel 2: Agent 4 Evidence Analysis Findings */}
                <div className="p-3.5 rounded-xl bg-white border border-slate-200 dark:bg-slate-900 dark:border-slate-800 space-y-2.5 shadow-2xs">
                  <div className="flex items-center justify-between pb-2 border-b border-slate-100 dark:border-slate-800">
                    <span className="text-xs font-bold text-slate-800 dark:text-slate-200 flex items-center gap-1.5">
                      <Brain className="h-3.5 w-3.5 text-blue-600" />
                      <span>Agent 4: Evidence Findings</span>
                    </span>
                    <Badge size="sm" variant="outline" className="text-[10px] font-mono">
                      {executionResult.collaboration.findings?.length || 0} claims
                    </Badge>
                  </div>

                  <p className="text-[11px] text-slate-500 dark:text-slate-400">
                    Factual claims mapped to source document chunks:
                  </p>

                  <div className="space-y-1.5 max-h-48 overflow-y-auto pr-1">
                    {executionResult.collaboration.findings?.length === 0 ? (
                      <div className="text-[11px] text-slate-400 italic">No structured claims extracted.</div>
                    ) : (
                      executionResult.collaboration.findings.map((f, i) => (
                        <div
                          key={f.finding_id || i}
                          className="p-2 rounded-lg bg-slate-50 dark:bg-slate-800/60 border border-slate-100 dark:border-slate-800 text-[11px] space-y-1"
                        >
                          <div className="font-medium text-slate-800 dark:text-slate-200 line-clamp-2">
                            {f.claim}
                          </div>
                          <div className="flex items-center justify-between text-[10px] text-slate-500">
                            <span>Confidence: {(f.confidence * 100).toFixed(0)}%</span>
                            {f.is_contradiction && (
                              <Badge size="sm" className="bg-red-100 text-red-800 text-[9px] px-1 py-0">
                                Contradiction
                              </Badge>
                            )}
                          </div>
                          {f.source_titles?.length > 0 && (
                            <div className="text-[9px] text-blue-600 dark:text-blue-400 truncate">
                              Source: {f.source_titles.join(', ')}
                            </div>
                          )}
                        </div>
                      ))
                    )}
                  </div>
                </div>

                {/* Panel 3: Agent 5 Verification Agent Audit */}
                <div className="p-3.5 rounded-xl bg-white border border-slate-200 dark:bg-slate-900 dark:border-slate-800 space-y-2.5 shadow-2xs">
                  <div className="flex items-center justify-between pb-2 border-b border-slate-100 dark:border-slate-800">
                    <span className="text-xs font-bold text-slate-800 dark:text-slate-200 flex items-center gap-1.5">
                      <ShieldCheck className="h-3.5 w-3.5 text-blue-600" />
                      <span>Agent 5: Verification Audit</span>
                    </span>
                    <Badge
                      size="sm"
                      className={`text-[10px] font-mono ${
                        executionResult.collaboration.verification?.is_verified
                          ? 'bg-emerald-100 text-emerald-800 dark:bg-emerald-900/50 dark:text-emerald-300'
                          : 'bg-amber-100 text-amber-800 dark:bg-amber-900/50 dark:text-amber-300'
                      }`}
                    >
                      {executionResult.collaboration.verification?.is_verified ? 'VERIFIED' : 'UNVERIFIED'}
                    </Badge>
                  </div>

                  <div className="space-y-2 text-[11px]">
                    <div className="flex items-center justify-between py-1 border-b border-slate-100 dark:border-slate-800">
                      <span className="text-slate-500">Recommendation:</span>
                      <span className="font-bold text-blue-600 dark:text-blue-400 uppercase text-[10px]">
                        {executionResult.collaboration.verification?.recommendation || 'PROCEED'}
                      </span>
                    </div>

                    <div className="flex items-center justify-between py-1 border-b border-slate-100 dark:border-slate-800">
                      <span className="text-slate-500">Citation Validity:</span>
                      <span className="font-mono font-semibold text-slate-800 dark:text-slate-200">
                        {((executionResult.collaboration.verification?.citation_validity_ratio || 1.0) * 100).toFixed(0)}%
                      </span>
                    </div>

                    <div className="flex items-center justify-between py-1 border-b border-slate-100 dark:border-slate-800">
                      <span className="text-slate-500">Supported Claims:</span>
                      <span className="font-semibold text-emerald-600">
                        {executionResult.collaboration.verification?.supported_claims?.length || 0}
                      </span>
                    </div>

                    {executionResult.collaboration.verification?.unsupported_claims && executionResult.collaboration.verification.unsupported_claims.length > 0 && (
                      <div className="flex items-center justify-between py-1">
                        <span className="text-slate-500">Unsupported:</span>
                        <span className="font-semibold text-red-600">
                          {executionResult.collaboration.verification.unsupported_claims.length}
                        </span>
                      </div>
                    )}
                  </div>
                </div>
              </div>
            </Card>
          )}

          {/* Results Grid: Grounded Answer & Node Telemetry Timeline */}
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            {/* Left Panel: Grounded AI Answer & Citations */}
            <Card className="p-6 border-slate-200 bg-white shadow-sm rounded-2xl dark:bg-slate-900 dark:border-slate-800 space-y-4">
              <div className="flex items-center justify-between pb-3 border-b border-slate-100 dark:border-slate-800">
                <div className="flex items-center gap-2">
                  <Sparkles className="h-4 w-4 text-blue-600" />
                  <h3 className="font-bold text-sm text-slate-900 dark:text-slate-100">
                    Grounded Answer Synthesis
                  </h3>
                </div>
                <Badge variant="outline" size="sm" className="font-mono text-[10px]">
                  {executionResult.model || 'grounded-synthesis'}
                </Badge>
              </div>

              {/* Answer Markdown View */}
              <div className="prose prose-sm dark:prose-invert max-w-none text-xs sm:text-sm text-slate-800 dark:text-slate-200 leading-relaxed bg-slate-50 dark:bg-slate-800/40 p-4 rounded-xl border border-slate-100 dark:border-slate-800">
                <MarkdownView content={executionResult.content} />
              </div>

              {/* Citations List */}
              {executionResult.citations && executionResult.citations.length > 0 && (
                <div className="space-y-3 pt-2">
                  <div className="flex items-center justify-between">
                    <span className="text-[11px] font-semibold text-slate-400 uppercase tracking-wider flex items-center gap-1.5">
                      <FileText className="h-3.5 w-3.5 text-blue-600" />
                      <span>Retrieved Evidence Citations ({executionResult.citations.length})</span>
                    </span>
                  </div>

                  <div className="space-y-2">
                    {executionResult.citations.map((c) => (
                      <CitationCard
                        key={`${c.id}-${c.documentId || c.title}`}
                        citation={c as CitationItem}
                      />
                    ))}
                  </div>
                </div>
              )}
            </Card>

            {/* Right Panel: Step Execution Trace & Telemetry */}
            <Card className="p-6 border-slate-200 bg-white shadow-sm rounded-2xl dark:bg-slate-900 dark:border-slate-800 space-y-4">
              <div className="flex items-center justify-between pb-3 border-b border-slate-100 dark:border-slate-800">
                <div className="flex items-center gap-2">
                  <Layers className="h-4 w-4 text-blue-600" />
                  <h3 className="font-bold text-sm text-slate-900 dark:text-slate-100">
                    LangGraph Node Execution Trace
                  </h3>
                </div>
                <Badge variant="outline" size="sm" className="bg-slate-100 text-slate-700 font-mono text-[10px] dark:bg-slate-800 dark:text-slate-300">
                  {executionResult.workflow_steps?.length || 0} Steps Executed
                </Badge>
              </div>

              {/* Timeline Steps List */}
              <div className="space-y-3">
                {executionResult.workflow_steps?.map((step, idx) => (
                  <div
                    key={`${step.step_id}-${idx}`}
                    className="flex items-start gap-3 p-3 rounded-xl border border-slate-100 bg-slate-50/70 hover:bg-slate-50 transition-colors dark:bg-slate-800/40 dark:border-slate-800 dark:hover:bg-slate-800/70"
                  >
                    <div className="mt-0.5 shrink-0">
                      {step.status === 'completed' ? (
                        <div className="flex h-5 w-5 items-center justify-center rounded-full bg-emerald-100 text-emerald-600 dark:bg-emerald-900/50 dark:text-emerald-400">
                          <CheckCircle2 className="h-3 w-3" />
                        </div>
                      ) : step.status === 'failed' ? (
                        <div className="flex h-5 w-5 items-center justify-center rounded-full bg-red-100 text-red-600 dark:bg-red-900/50 dark:text-red-400">
                          <AlertTriangle className="h-3 w-3" />
                        </div>
                      ) : (
                        <div className="flex h-5 w-5 items-center justify-center rounded-full bg-blue-100 text-blue-600 dark:bg-blue-900/50 dark:text-blue-400">
                          <RefreshCw className="h-3 w-3" />
                        </div>
                      )}
                    </div>

                    <div className="flex-1 space-y-1">
                      <div className="flex items-center justify-between">
                        <span className="font-semibold text-xs text-slate-900 dark:text-slate-100">
                          {step.name}
                        </span>
                        <span className="font-mono text-[10px] text-slate-500 dark:text-slate-400 font-medium">
                          {step.duration_ms.toFixed(1)} ms
                        </span>
                      </div>
                      <p className="text-[11px] text-slate-600 dark:text-slate-400 leading-relaxed">
                        {step.description || `Node ${step.step_id} execution finished`}
                      </p>
                    </div>
                  </div>
                ))}
              </div>
            </Card>
          </div>
        </div>
      )}
    </div>
  );
}
