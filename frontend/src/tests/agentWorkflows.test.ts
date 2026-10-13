import { describe, it, expect, vi, beforeEach } from 'vitest';
import { agentService } from '@/services/agentService';
import * as apiModule from '@/services/api';

describe('Agent Workflows Service & Simulation (Phase 7)', () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it('successfully executes workflow simulation via /agents/simulate', async () => {
    const mockSimulationResponse = {
      success: true,
      data: {
        id: 'm-agent-run-123',
        role: 'assistant',
        content: 'Python operators include arithmetic (+, -, *, /) and comparison (==, !=, >, <) [1].',
        status: 'answered',
        timestamp: '2026-10-10T10:00:00Z',
        knowledge_base_id: 'kb-test-uuid',
        citations: [
          {
            id: 1,
            chunk_id: 'chunk-1',
            document_id: 'doc-1',
            title: 'Python_Basics.pdf',
            section: '2. Operators',
            page: 2,
            snippet: 'Python operators evaluate expressions and return values.',
            relevance_score: 0.92,
          },
        ],
        confidence: null,
        verification_status: 'grounded_evidence',
        is_insufficient_evidence: false,
        retrieval_latency: {
          vector_ms: 18.2,
          lexical_ms: 10.5,
          fusion_ms: 2.1,
          rerank_ms: 32.4,
          total_ms: 63.2,
        },
        generation_ms: 124.0,
        total_ms: 195.4,
        model: 'grounded-synthesis-engine',
        retry_count: 0,
        workflow_steps: [
          {
            step_id: 'query_analysis',
            name: 'Query Analysis',
            status: 'completed',
            duration_ms: 1.5,
            description: 'Extracted 2 key search terms',
          },
          {
            step_id: 'scope_authorization',
            name: 'Scope & Permission Validation',
            status: 'completed',
            duration_ms: 3.2,
            description: 'Authorized knowledge base: Python Docs',
          },
          {
            step_id: 'retrieval_strategy',
            name: 'Retrieval Strategy Selection',
            status: 'completed',
            duration_ms: 0.8,
            description: 'Initial pass: Hybrid strategy',
          },
          {
            step_id: 'retrieval',
            name: 'Hybrid Evidence Retrieval',
            status: 'completed',
            duration_ms: 63.2,
            description: 'Retrieved 5 chunks',
          },
          {
            step_id: 'evidence_assessment',
            name: 'Evidence Assessment',
            status: 'completed',
            duration_ms: 1.1,
            description: 'Confirmed relevant evidence across 5 scoped chunks.',
          },
          {
            step_id: 'grounded_generation',
            name: 'Grounded Answer Generation',
            status: 'completed',
            duration_ms: 124.0,
            description: 'Synthesized answer using grounded-synthesis-engine',
          },
          {
            step_id: 'citation_validation',
            name: 'Citation & Provenance Auditing',
            status: 'completed',
            duration_ms: 1.2,
            description: 'Validated 1 cited sources',
          },
          {
            step_id: 'finalization',
            name: 'Workflow Finalization',
            status: 'completed',
            duration_ms: 0.4,
            description: 'Compiled structured response with full evidence telemetry',
          },
        ],
      },
    };

    const spy = vi.spyOn(apiModule, 'apiClient').mockResolvedValue(mockSimulationResponse);

    const payload = {
      knowledge_base_id: 'kb-test-uuid',
      prompt: 'What are operators in Python?',
      top_k: 5,
      enable_reranking: true,
    };

    const result = await agentService.simulateWorkflow(payload);

    expect(spy).toHaveBeenCalledWith('/agents/simulate', {
      method: 'POST',
      body: JSON.stringify(payload),
    });

    expect(result.status).toBe('answered');
    expect(result.is_insufficient_evidence).toBe(false);
    expect(result.citations).toHaveLength(1);
    expect(result.workflow_steps).toHaveLength(8);
    expect(result.workflow_steps?.[0].step_id).toBe('query_analysis');
  });

  it('handles insufficient evidence with self-healing retry trace', async () => {
    const mockInsufficientResponse = {
      success: true,
      data: {
        id: 'm-agent-insufficient',
        role: 'assistant',
        content: 'I could not find sufficient matching information in the authorized documents to answer your question.',
        status: 'insufficient_evidence',
        timestamp: '2026-10-10T10:01:00Z',
        knowledge_base_id: 'kb-test-uuid',
        citations: [],
        confidence: null,
        verification_status: 'insufficient_evidence',
        is_insufficient_evidence: true,
        retrieval_latency: null,
        generation_ms: 1.5,
        total_ms: 110.0,
        model: 'grounded-synthesis-engine',
        retry_count: 1,
        workflow_steps: [
          {
            step_id: 'query_analysis',
            name: 'Query Analysis',
            status: 'completed',
            duration_ms: 1.2,
            description: 'Extracted 3 key search terms',
          },
          {
            step_id: 'scope_authorization',
            name: 'Scope & Permission Validation',
            status: 'completed',
            duration_ms: 2.5,
          },
          {
            step_id: 'retrieval_strategy',
            name: 'Retrieval Strategy Selection',
            status: 'completed',
            duration_ms: 0.5,
          },
          {
            step_id: 'retrieval',
            name: 'Hybrid Evidence Retrieval',
            status: 'completed',
            duration_ms: 45.0,
          },
          {
            step_id: 'evidence_assessment',
            name: 'Evidence Assessment',
            status: 'completed',
            duration_ms: 1.0,
            description: 'Outcome: insufficient',
          },
          {
            step_id: 'bounded_retry',
            name: 'Bounded Retrieval Retry',
            status: 'completed',
            duration_ms: 0.3,
            description: 'Triggering bounded retry attempt #1 with adapted strategy parameters',
          },
          {
            step_id: 'retrieval_strategy',
            name: 'Retrieval Strategy Selection',
            status: 'completed',
            duration_ms: 0.5,
          },
          {
            step_id: 'retrieval',
            name: 'Hybrid Evidence Retrieval',
            status: 'completed',
            duration_ms: 55.0,
          },
          {
            step_id: 'evidence_assessment',
            name: 'Evidence Assessment',
            status: 'completed',
            duration_ms: 1.0,
            description: 'Outcome: insufficient',
          },
          {
            step_id: 'grounded_generation',
            name: 'Grounded Answer Generation',
            status: 'completed',
            duration_ms: 1.5,
            description: 'Generated insufficient evidence limitation response',
          },
          {
            step_id: 'citation_validation',
            name: 'Citation & Provenance Auditing',
            status: 'completed',
            duration_ms: 0.5,
            description: 'Citation validation bypassed for insufficient evidence',
          },
          {
            step_id: 'finalization',
            name: 'Workflow Finalization',
            status: 'completed',
            duration_ms: 0.5,
          },
        ],
      },
    };

    vi.spyOn(apiModule, 'apiClient').mockResolvedValue(mockInsufficientResponse);

    const result = await agentService.simulateWorkflow({
      knowledge_base_id: 'kb-test-uuid',
      prompt: 'Unrelated astrophysics query',
    });

    expect(result.status).toBe('insufficient_evidence');
    expect(result.is_insufficient_evidence).toBe(true);
    expect(result.retry_count).toBe(1);
    expect(result.workflow_steps?.some((s) => s.step_id === 'bounded_retry')).toBe(true);
  });

  it('propagates ApiError when LangGraph is unconfigured or request fails', async () => {
    vi.spyOn(apiModule, 'apiClient').mockRejectedValue(
      new apiModule.ApiError(
        'LangGraph execution framework is not installed or configured on the server.',
        'LANGGRAPH_NOT_CONFIGURED',
        530
      )
    );

    await expect(
      agentService.simulateWorkflow({
        knowledge_base_id: 'kb-test-uuid',
        prompt: 'Test query',
      })
    ).rejects.toThrow('LangGraph execution framework is not installed or configured on the server.');
  });

  it('fetches active LangGraph topology metadata from /agents/graph', async () => {
    const mockTopologyResponse = {
      success: true,
      data: {
        graph_id: 'agentic_rag_v1',
        framework: 'langgraph',
        framework_version: '1.2.14',
        status: 'ready',
        recursion_limit: 15,
        max_retries: 1,
        nodes: [
          {
            id: 'query_analysis',
            name: 'Query Analysis',
            role: 'Intent evaluation',
            phase: 'Phase 7',
          },
        ],
        conditional_edges: [
          {
            from: 'query_analysis',
            condition: 'is_ambiguous',
            branches: ['grounded_generation', 'scope_authorization'],
          },
        ],
      },
    };

    const spy = vi.spyOn(apiModule, 'apiClient').mockResolvedValue(mockTopologyResponse);

    const topology = await agentService.getGraphTopology();
    expect(spy).toHaveBeenCalledWith('/agents/graph');
    expect(topology.framework).toBe('langgraph');
    expect(topology.status).toBe('ready');
    expect(topology.nodes).toHaveLength(1);
  });
});
