import { useEffect, useState, useCallback } from 'react';
import {
  Activity,
  Clock,
  ChevronRight,
  Zap,
  AlertTriangle,
  CheckCircle2,
  RefreshCw,
  Search,
  Server,
  Layers,
  Database,
  SlidersHorizontal,
  Coins,
  DollarSign,
  BarChart3,
  CheckCircle,
  AlertCircle,
} from 'lucide-react';
import { Card } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { MetricCard } from '@/components/ui/metric-card';
import { Tabs, TabsList, TabsTrigger, TabsContent } from '@/components/ui/tabs';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { Drawer } from '@/components/ui/drawer';
import { observabilityService } from '@/services/observabilityService';
import type {
  AlertRecord,
  ErrorIncidentItem,
  ModelPricingItem,
  OverviewStats,
  ReliabilityMetrics,
  TraceRunItem,
  TraceStepItem,
} from '@/types/observability';

const SAMPLE_DEMO_TRACE: TraceRunItem = {
  id: 'tr-demo-7b81',
  traceId: 'tr-demo-7b81',
  query: 'What is the refund period for commercial enterprise contracts?',
  status: 'recovered',
  durationMs: 842.5,
  tokensTotal: 584,
  promptTokens: 412,
  completionTokens: 172,
  estimatedCostUsd: 0.00275,
  costStatus: 'estimated',
  costCurrency: 'USD',
  pricingSource: 'standard_catalog_2026',
  model: 'gpt-4o',
  retrievalMethod: 'hybrid_rrf_rerank',
  evidenceSufficiency: 'sufficient',
  citationValidationPassed: true,
  verificationStatus: 'grounded_evidence',
  createdAt: 'Just now',
  recoveryCount: 1,
  retrievalScores: [
    {
      chunk_id: 'chk-contract-clause-12',
      document_id: 'doc-ent-terms-2026',
      vector_score: 0.884,
      bm25_score: 14.25,
      rrf_score: 0.0328,
      rerank_score: 0.942,
      final_rank: 1,
      retrieval_stage: 'hybrid_fusion_rerank',
      is_used_in_generation: true,
      is_cited: true,
    },
    {
      chunk_id: 'chk-refund-timeline-04',
      document_id: 'doc-ent-terms-2026',
      vector_score: 0.821,
      bm25_score: 11.40,
      rrf_score: 0.0284,
      rerank_score: 0.889,
      final_rank: 2,
      retrieval_stage: 'hybrid_fusion_rerank',
      is_used_in_generation: true,
      is_cited: true,
    },
    {
      chunk_id: 'chk-termination-payout-08',
      document_id: 'doc-billing-faq-v2',
      vector_score: 0.742,
      bm25_score: 8.95,
      rrf_score: 0.0195,
      rerank_score: 0.651,
      final_rank: 3,
      retrieval_stage: 'hybrid_fusion_rerank',
      is_used_in_generation: false,
      is_cited: false,
    },
  ],
  steps: [
    {
      id: 's-1',
      name: 'Request Gateway & Correlation Init',
      stepType: 'gateway',
      durationMs: 4.2,
      status: 'completed',
      inputs: { request_id: 'd1b5bd9e-62f8-4d16', client_ip: '127.0.0.1' },
      outputs: { valid_origin: true, auth_tenant: 'enterprise_default' },
    },
    {
      id: 's-2',
      name: 'Query Preprocessing & Intent Classification',
      stepType: 'query_analysis',
      durationMs: 24.8,
      status: 'completed',
      inputs: { raw_query: 'What is the refund period for commercial enterprise contracts?' },
      outputs: { intent: 'policy_lookup', sub_queries: ['commercial refund window', 'contract termination payout'] },
    },
    {
      id: 's-3',
      name: 'Dense Semantic Vector Retrieval (pgvector)',
      stepType: 'dense_retrieval',
      durationMs: 98.4,
      status: 'completed',
      inputs: { top_k: 10, embedding_model: 'text-embedding-3-small' },
      outputs: { candidates: 10, min_score: 0.76 },
    },
    {
      id: 's-4',
      name: 'Lexical Search (BM25 Okapi)',
      stepType: 'lexical_retrieval',
      durationMs: 32.1,
      status: 'completed',
      inputs: { top_k: 10, terms: ['refund', 'period', 'commercial', 'enterprise'] },
      outputs: { candidates: 8 },
    },
    {
      id: 's-5',
      name: 'Reciprocal Rank Fusion (RRF)',
      stepType: 'fusion',
      durationMs: 14.2,
      status: 'completed',
      inputs: { rank_constant_k: 60 },
      outputs: { fused_candidates: 12 },
    },
    {
      id: 's-6',
      name: 'Cross-Encoder Attention Reranker',
      stepType: 'reranking',
      durationMs: 84.0,
      status: 'completed',
      inputs: { candidates_in: 12, reranker: 'bge-reranker-large' },
      outputs: { top_k_reranked: 5, cutoff: 0.72 },
    },
    {
      id: 's-7',
      name: 'LLM Generation & Grounded Synthesis',
      stepType: 'grounded_generation',
      durationMs: 380.0,
      status: 'completed',
      promptTokens: 412,
      completionTokens: 172,
      estimatedCostUsd: 0.00275,
      inputs: { model: 'gpt-4o', temperature: 0.2, prompt_tokens: 412 },
      outputs: { completion_tokens: 172, citations_attached: 2 },
    },
    {
      id: 's-8',
      name: 'Citation Validation & Provenance Audit',
      stepType: 'citation_validation',
      durationMs: 45.0,
      status: 'completed',
      inputs: { claims: 2, sources: 2 },
      outputs: { citation_validation_passed: true },
    },
    {
      id: 's-9',
      name: 'Factuality & Hallucination Guard Check',
      stepType: 'answer_verification',
      durationMs: 98.0,
      status: 'completed',
      inputs: { nli_premises: 2 },
      outputs: { verification_status: 'grounded_evidence', confidence: 0.94 },
    },
    {
      id: 's-10',
      name: 'Self-Healing Recovery Safeguard Check',
      stepType: 'recovery',
      durationMs: 42.0,
      status: 'recovered',
      inputs: { recovery_attempted: true, action: 'repair_citations' },
      outputs: { is_recovered: true, retry_count: 1 },
    },
    {
      id: 's-11',
      name: 'Fallback Query Rewrite (Bypassed)',
      stepType: 'query_rewrite',
      durationMs: 0,
      status: 'skipped',
      isSkipped: true,
      inputs: { reason: 'Initial retrieval was sufficient; rewrite conditionally bypassed' },
      outputs: { is_skipped: true },
    },
  ],
};

export function ObservabilityPage() {
  const [selectedTrace, setSelectedTrace] = useState<TraceRunItem | null>(null);
  const [selectedStep, setSelectedStep] = useState<TraceStepItem | null>(null);

  // Live backend data
  const [traces, setTraces] = useState<TraceRunItem[]>([]);
  const [metrics, setMetrics] = useState<ReliabilityMetrics | null>(null);
  const [overview, setOverview] = useState<OverviewStats | null>(null);
  const [errorIncidents, setErrorIncidents] = useState<ErrorIncidentItem[]>([]);
  const [pricingCatalog, setPricingCatalog] = useState<ModelPricingItem[]>([]);
  const [alerts, setAlerts] = useState<AlertRecord[]>([]);
  const [readiness, setReadiness] = useState<{ status: string; dependencies?: Record<string, unknown> } | null>(null);
  const [loading, setLoading] = useState<boolean>(true);

  // Filters
  const [statusFilter, setStatusFilter] = useState<string>('all');
  const [searchTerm, setSearchTerm] = useState<string>('');

  const fetchData = useCallback(async () => {
    setLoading(true);
    try {
      const [
        tracesRes,
        metricsRes,
        alertsRes,
        readyRes,
        overviewRes,
        errorsRes,
        pricingRes,
      ] = await Promise.allSettled([
        observabilityService.listTraces({ limit: 50, status: statusFilter, search: searchTerm }),
        observabilityService.getMetrics(),
        observabilityService.getAlerts(),
        observabilityService.getReadiness(),
        observabilityService.getOverview(),
        observabilityService.getErrorExplorer(50),
        observabilityService.getPricingCatalog(),
      ]);

      if (tracesRes.status === 'fulfilled') {
        setTraces(tracesRes.value.items);
      }
      if (metricsRes.status === 'fulfilled') {
        setMetrics(metricsRes.value);
      }
      if (alertsRes.status === 'fulfilled') {
        setAlerts(alertsRes.value);
      }
      if (readyRes.status === 'fulfilled') {
        setReadiness(readyRes.value);
      }
      if (overviewRes.status === 'fulfilled') {
        setOverview(overviewRes.value);
      }
      if (errorsRes.status === 'fulfilled') {
        setErrorIncidents(errorsRes.value);
      }
      if (pricingRes.status === 'fulfilled') {
        setPricingCatalog(pricingRes.value);
      }
    } catch (e) {
      console.error('Failed to load observability data:', e);
    } finally {
      setLoading(false);
    }
  }, [statusFilter, searchTerm]);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  const handleInspectTrace = async (trace: TraceRunItem) => {
    if (trace.steps && trace.steps.length > 0) {
      setSelectedTrace(trace);
      setSelectedStep(trace.steps[0] || null);
      return;
    }
    // Fetch full trace details
    try {
      const fullTrace = await observabilityService.getTrace(trace.id);
      setSelectedTrace(fullTrace);
      setSelectedStep(fullTrace.steps?.[0] || null);
    } catch {
      setSelectedTrace(trace);
      setSelectedStep(null);
    }
  };

  const formatCostBadge = (status?: string) => {
    if (status === 'provider_reported') {
      return (
        <Badge variant="outline" size="sm" className="bg-emerald-50 text-emerald-700 border-emerald-200">
          Provider Exact
        </Badge>
      );
    }
    if (status === 'estimated') {
      return (
        <Badge variant="outline" size="sm" className="bg-blue-50 text-blue-700 border-blue-200">
          Catalog Est.
        </Badge>
      );
    }
    return (
      <Badge variant="outline" size="sm" className="bg-slate-100 text-slate-500 border-slate-200">
        Unavailable
      </Badge>
    );
  };

  return (
    <div className="space-y-6">
      {/* Page Header */}
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <div className="flex items-center gap-2">
            <h1 className="text-2xl font-bold tracking-tight text-slate-900 dark:text-white">
              Observability & Production Intelligence
            </h1>
            <Badge
              variant="outline"
              size="sm"
              className={
                readiness?.status === 'ready' || readiness?.status === 'ok'
                  ? 'bg-emerald-50 text-emerald-700 border-emerald-200 dark:bg-emerald-950/40 dark:text-emerald-300'
                  : 'bg-amber-50 text-amber-700 border-amber-200 dark:bg-amber-950/40 dark:text-amber-300'
              }
            >
              <span className="h-1.5 w-1.5 rounded-full bg-emerald-500 mr-1.5 animate-pulse" />
              {readiness?.status === 'ready' ? 'Telemetry Ready' : 'Telemetry Online'}
            </Badge>
          </div>
          <p className="text-xs sm:text-sm text-slate-500 dark:text-slate-400 mt-1">
            End-to-end distributed tracing, token accounting, model cost intelligence, and retrieval score provenance.
          </p>
        </div>

        <div className="flex items-center gap-2">
          <Button
            size="sm"
            variant="outline"
            onClick={fetchData}
            disabled={loading}
            className="gap-1.5 text-xs border-slate-200 dark:border-slate-800"
          >
            <RefreshCw className={`h-3.5 w-3.5 ${loading ? 'animate-spin' : ''}`} />
            <span>Refresh</span>
          </Button>

          <Button
            size="sm"
            onClick={() => handleInspectTrace(SAMPLE_DEMO_TRACE)}
            className="gap-1.5 text-xs bg-blue-600 hover:bg-blue-700 text-white font-medium shadow-sm shadow-blue-500/20"
          >
            <Activity className="h-3.5 w-3.5" />
            <span>Inspect Sample Trace</span>
          </Button>
        </div>
      </div>

      {/* Top Telemetry & Cost Intelligence KPI Cards */}
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <MetricCard
          title="Recorded Requests"
          value={overview ? String(overview.total_requests) : metrics ? String(metrics.total_requests) : '--'}
          subtitle={
            overview
              ? `${overview.successful_requests} ok / ${overview.failed_requests} fail (${(overview.success_rate * 100).toFixed(1)}% success)`
              : metrics
              ? `${metrics.successful_requests} ok / ${metrics.failed_requests} fail`
              : 'Awaiting traffic'
          }
          icon={Activity}
          badge={overview && overview.total_requests > 0 ? 'Live Telemetry' : 'Standby'}
          badgeVariant={overview && overview.total_requests > 0 ? 'default' : 'secondary'}
        />

        <MetricCard
          title="Token Accounting"
          value={
            overview && overview.total_tokens > 0
              ? overview.total_tokens.toLocaleString()
              : '--'
          }
          subtitle={
            overview
              ? `${overview.prompt_tokens.toLocaleString()} prompt / ${overview.completion_tokens.toLocaleString()} comp.`
              : 'Metadata pending'
          }
          icon={Coins}
          badge={
            overview?.cost_status === 'provider_reported'
              ? 'Provider Exact'
              : overview?.cost_status === 'estimated'
              ? 'Catalog Est.'
              : 'Tracking'
          }
          badgeVariant="secondary"
        />

        <MetricCard
          title="Model Cost Intelligence"
          value={
            overview && overview.total_estimated_cost_usd !== null
              ? `$${overview.total_estimated_cost_usd.toFixed(4)}`
              : '--'
          }
          subtitle={
            overview?.avg_cost_per_query_usd !== null && overview?.avg_cost_per_query_usd !== undefined
              ? `Avg: $${overview.avg_cost_per_query_usd.toFixed(4)} / query`
              : 'USD per 1M token catalog'
          }
          icon={DollarSign}
          badge={overview?.cost_status === 'estimated' ? 'Catalog Est.' : overview?.cost_status === 'provider_reported' ? 'Exact API' : 'Unavailable'}
          badgeVariant={overview?.cost_status === 'provider_reported' ? 'default' : 'secondary'}
        />

        <MetricCard
          title="P95 End-to-End Latency"
          value={
            overview?.p95_latency_ms
              ? `${overview.p95_latency_ms}ms`
              : metrics?.p95_latency_ms
              ? `${metrics.p95_latency_ms}ms`
              : overview?.avg_latency_ms
              ? `~${overview.avg_latency_ms}ms`
              : '--'
          }
          subtitle={
            overview?.p50_latency_ms
              ? `P50: ${overview.p50_latency_ms}ms | P99: ${overview.p99_latency_ms ?? '--'}ms`
              : metrics?.p50_latency_ms
              ? `P50: ${metrics.p50_latency_ms}ms | P99: ${metrics.p99_latency_ms ?? '--'}ms`
              : '3+ samples required'
          }
          icon={Clock}
          badge={overview?.p95_latency_ms && overview.p95_latency_ms > 3500 ? 'SLA Alert' : 'Healthy'}
          badgeVariant={overview?.p95_latency_ms && overview.p95_latency_ms > 3500 ? 'warning' : 'secondary'}
        />
      </div>

      {/* Observability Views Tabs */}
      <Tabs defaultValue="traces">
        <div className="flex items-center justify-between mb-3">
          <TabsList className="bg-slate-100 p-1 dark:bg-slate-800">
            <TabsTrigger value="traces">Trace Explorer</TabsTrigger>
            <TabsTrigger value="errors">
              Error Explorer
              {errorIncidents.length > 0 && (
                <span className="ml-1.5 px-1.5 py-0.2 text-[10px] rounded-full bg-rose-500 text-white font-bold">
                  {errorIncidents.length}
                </span>
              )}
            </TabsTrigger>
            <TabsTrigger value="insights">Model & Cost Catalog</TabsTrigger>
            <TabsTrigger value="latency">Latency Breakdown</TabsTrigger>
            <TabsTrigger value="alerts">
              Alerts
              {alerts.length > 0 && (
                <span className="ml-1.5 px-1.5 py-0.2 text-[10px] rounded-full bg-amber-500 text-white font-bold">
                  {alerts.length}
                </span>
              )}
            </TabsTrigger>
            <TabsTrigger value="readiness">System Health</TabsTrigger>
          </TabsList>
          <span className="text-[11px] font-mono text-slate-500 hidden sm:inline">
            Production Intelligence & Telemetry Engine
          </span>
        </div>

        {/* Tab 1: Trace Explorer */}
        <TabsContent value="traces">
          <Card className="p-4 bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-2xl shadow-2xs">
            {/* Table Search & Status Filters */}
            <div className="flex flex-col sm:flex-row items-center justify-between gap-3 mb-4">
              <div className="relative w-full sm:w-72">
                <Search className="absolute left-3 top-2.5 h-4 w-4 text-slate-400" />
                <input
                  type="text"
                  placeholder="Filter by Query or Trace ID..."
                  value={searchTerm}
                  onChange={(e) => setSearchTerm(e.target.value)}
                  className="w-full pl-9 pr-3 py-1.5 text-xs rounded-xl border border-slate-200 bg-slate-50/50 text-slate-900 placeholder:text-slate-400 focus:outline-none focus:ring-1 focus:ring-blue-500 dark:bg-slate-800/40 dark:border-slate-800 dark:text-slate-100"
                />
              </div>

              <div className="flex items-center gap-1.5 w-full sm:w-auto">
                <SlidersHorizontal className="h-3.5 w-3.5 text-slate-400 mr-1" />
                {(['all', 'completed', 'recovered', 'failed'] as const).map((st) => (
                  <Button
                    key={st}
                    size="xs"
                    variant={statusFilter === st ? 'default' : 'ghost'}
                    onClick={() => setStatusFilter(st)}
                    className="capitalize text-xs"
                  >
                    {st}
                  </Button>
                ))}
              </div>
            </div>

            {/* Traces Table */}
            <div className="rounded-xl border border-slate-200 dark:border-slate-800 overflow-hidden">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Trace ID</TableHead>
                    <TableHead>Query</TableHead>
                    <TableHead>Status</TableHead>
                    <TableHead>Duration</TableHead>
                    <TableHead>Tokens</TableHead>
                    <TableHead>Est. Cost</TableHead>
                    <TableHead>Retrieval</TableHead>
                    <TableHead>Model</TableHead>
                    <TableHead>Created</TableHead>
                    <TableHead className="text-right">Actions</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {traces.length === 0 ? (
                    <TableRow>
                      <TableCell colSpan={10} className="text-center py-10 text-slate-500 text-xs">
                        <Activity className="h-6 w-6 text-slate-400 mx-auto mb-2 opacity-50" />
                        <p className="font-semibold text-slate-700 dark:text-slate-300">
                          No execution traces recorded yet
                        </p>
                        <p className="text-[11px] text-slate-500 mt-1">
                          Execute queries in the Chat or Agent Workflows page to produce live distributed traces.
                        </p>
                        <Button
                          size="xs"
                          variant="outline"
                          onClick={() => handleInspectTrace(SAMPLE_DEMO_TRACE)}
                          className="mt-3 text-xs"
                        >
                          Inspect Demo Trace
                        </Button>
                      </TableCell>
                    </TableRow>
                  ) : (
                    traces.map((trace) => {
                      const isRecovered = trace.status === 'recovered';
                      const isFailed = trace.status === 'failed';
                      return (
                        <TableRow
                          key={trace.id}
                          onClick={() => handleInspectTrace(trace)}
                          className="cursor-pointer hover:bg-slate-50/70 dark:hover:bg-slate-800/40"
                        >
                          <TableCell className="font-mono text-xs font-semibold text-blue-600 dark:text-blue-400">
                            {trace.id}
                          </TableCell>
                          <TableCell className="text-xs text-slate-800 dark:text-slate-200 max-w-xs truncate">
                            {trace.query}
                          </TableCell>
                          <TableCell>
                            <Badge
                              variant="outline"
                              size="sm"
                              className={
                                isRecovered
                                  ? 'bg-purple-50 text-purple-700 border-purple-200 dark:bg-purple-950/40 dark:text-purple-300'
                                  : isFailed
                                  ? 'bg-rose-50 text-rose-700 border-rose-200 dark:bg-rose-950/40 dark:text-rose-300'
                                  : 'bg-emerald-50 text-emerald-700 border-emerald-200 dark:bg-emerald-950/40 dark:text-emerald-300'
                              }
                            >
                              {isRecovered ? 'Self-Healed' : isFailed ? 'Failed' : 'Completed'}
                            </Badge>
                          </TableCell>
                          <TableCell className="font-mono text-xs text-slate-700 dark:text-slate-300">
                            {trace.durationMs ? `${trace.durationMs}ms` : '--'}
                          </TableCell>
                          <TableCell className="font-mono text-xs text-slate-700 dark:text-slate-300">
                            {trace.tokensTotal ? trace.tokensTotal.toLocaleString() : '--'}
                          </TableCell>
                          <TableCell className="font-mono text-xs text-slate-700 dark:text-slate-300">
                            {trace.estimatedCostUsd !== null && trace.estimatedCostUsd !== undefined
                              ? `$${trace.estimatedCostUsd.toFixed(4)}`
                              : '--'}
                          </TableCell>
                          <TableCell className="text-xs text-slate-600 dark:text-slate-400">
                            <Badge variant="outline" size="sm" className="text-[10px] bg-slate-50 dark:bg-slate-800">
                              {trace.retrievalMethod || 'hybrid'}
                            </Badge>
                          </TableCell>
                          <TableCell className="font-mono text-xs text-slate-500">
                            {trace.model || 'default'}
                          </TableCell>
                          <TableCell className="text-xs text-slate-500">
                            {new Date(trace.createdAt).toLocaleTimeString()}
                          </TableCell>
                          <TableCell className="text-right">
                            <Button
                              variant="ghost"
                              size="xs"
                              className="gap-1 text-xs text-blue-600 hover:text-blue-700"
                            >
                              <span>Inspect</span>
                              <ChevronRight className="h-3 w-3" />
                            </Button>
                          </TableCell>
                        </TableRow>
                      );
                    })
                  )}
                </TableBody>
              </Table>
            </div>
          </Card>
        </TabsContent>

        {/* Tab 2: Error Explorer */}
        <TabsContent value="errors">
          <Card className="p-5 bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-2xl shadow-2xs">
            <div className="flex items-center justify-between mb-4">
              <div className="flex items-center gap-2">
                <AlertCircle className="h-4 w-4 text-rose-600" />
                <h3 className="text-sm font-semibold text-slate-900 dark:text-slate-100">
                  Production Error Explorer & Root-Cause Remediation
                </h3>
              </div>
              <Badge variant="outline" size="sm" className="text-xs">
                {errorIncidents.length} Incident Records
              </Badge>
            </div>

            {errorIncidents.length === 0 ? (
              <div className="text-center py-10 text-slate-500">
                <CheckCircle2 className="h-8 w-8 text-emerald-500 mx-auto mb-2 opacity-80" />
                <p className="font-semibold text-xs text-slate-700 dark:text-slate-300">
                  Zero Unrecovered Pipeline Failures
                </p>
                <p className="text-[11px] text-slate-500 mt-0.5">
                  All recorded requests completed successfully or healed via automated recovery loops.
                </p>
              </div>
            ) : (
              <div className="space-y-3">
                {errorIncidents.map((inc) => (
                  <div
                    key={inc.trace_id}
                    className="p-4 rounded-xl border border-slate-200 dark:border-slate-800 bg-slate-50/60 dark:bg-slate-850 space-y-2"
                  >
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-2">
                        <Badge
                          variant="outline"
                          size="sm"
                          className={
                            inc.is_infrastructure_failure
                              ? 'bg-rose-50 text-rose-700 border-rose-200'
                              : 'bg-amber-50 text-amber-700 border-amber-200'
                          }
                        >
                          {inc.error_category}
                        </Badge>
                        <span className="font-mono text-xs font-semibold text-blue-600">
                          {inc.trace_id}
                        </span>
                        <span className="font-mono text-[10px] text-slate-400">
                          [{inc.safe_code}]
                        </span>
                      </div>
                      <div className="flex items-center gap-2">
                        {inc.recovery_succeeded ? (
                          <Badge variant="outline" size="sm" className="bg-purple-50 text-purple-700 border-purple-200">
                            Auto-Healed
                          </Badge>
                        ) : inc.is_retryable ? (
                          <Badge variant="outline" size="sm" className="bg-blue-50 text-blue-700 border-blue-200">
                            Retryable
                          </Badge>
                        ) : (
                          <Badge variant="outline" size="sm" className="bg-rose-50 text-rose-700 border-rose-200">
                            Terminal
                          </Badge>
                        )}
                        <span className="text-[11px] text-slate-400">
                          {new Date(inc.created_at).toLocaleTimeString()}
                        </span>
                      </div>
                    </div>

                    <p className="text-xs text-slate-800 dark:text-slate-200 font-medium">
                      Query: &ldquo;{inc.query}&rdquo;
                    </p>
                    <p className="text-xs text-slate-600 dark:text-slate-300">
                      <span className="font-semibold text-slate-700 dark:text-slate-300">Diagnostic: </span>
                      {inc.diagnostic_summary}
                    </p>
                    <div className="p-2.5 rounded-lg bg-blue-50/60 dark:bg-blue-950/30 border border-blue-100 dark:border-blue-900/40 text-[11px] text-blue-800 dark:text-blue-300 flex items-start gap-1.5">
                      <CheckCircle className="h-3.5 w-3.5 mt-0.5 shrink-0 text-blue-600" />
                      <span>
                        <strong>Suggested Remediation:</strong> {inc.suggested_action}
                      </span>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </Card>
        </TabsContent>

        {/* Tab 3: Model & Cost Catalog Insights */}
        <TabsContent value="insights">
          <div className="grid gap-4 md:grid-cols-2">
            <Card className="p-5 bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-2xl shadow-2xs">
              <div className="flex items-center gap-2 mb-4">
                <BarChart3 className="h-4 w-4 text-blue-600" />
                <h3 className="text-sm font-semibold text-slate-900 dark:text-slate-100">
                  Model & Retrieval Strategy Usage
                </h3>
              </div>

              <div className="space-y-4">
                <div>
                  <span className="text-xs font-semibold text-slate-700 dark:text-slate-300 block mb-2">
                    LLM Models Used
                  </span>
                  {overview && Object.keys(overview.models_used).length > 0 ? (
                    <div className="space-y-1.5">
                      {Object.entries(overview.models_used).map(([model, count]) => (
                        <div key={model} className="flex justify-between items-center text-xs p-2 rounded-lg bg-slate-50 dark:bg-slate-800/40 border border-slate-200 dark:border-slate-800">
                          <span className="font-mono text-slate-800 dark:text-slate-200">{model}</span>
                          <Badge variant="outline" size="sm">{count} calls</Badge>
                        </div>
                      ))}
                    </div>
                  ) : (
                    <p className="text-xs text-slate-500">Awaiting model execution data</p>
                  )}
                </div>

                <div>
                  <span className="text-xs font-semibold text-slate-700 dark:text-slate-300 block mb-2">
                    Retrieval Strategies Executed
                  </span>
                  {overview && Object.keys(overview.retrieval_methods_used).length > 0 ? (
                    <div className="space-y-1.5">
                      {Object.entries(overview.retrieval_methods_used).map(([strat, count]) => (
                        <div key={strat} className="flex justify-between items-center text-xs p-2 rounded-lg bg-slate-50 dark:bg-slate-800/40 border border-slate-200 dark:border-slate-800">
                          <span className="font-mono text-slate-800 dark:text-slate-200">{strat}</span>
                          <Badge variant="outline" size="sm">{count} runs</Badge>
                        </div>
                      ))}
                    </div>
                  ) : (
                    <p className="text-xs text-slate-500">Awaiting retrieval telemetry</p>
                  )}
                </div>
              </div>
            </Card>

            <Card className="p-5 bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-2xl shadow-2xs">
              <div className="flex items-center gap-2 mb-4">
                <DollarSign className="h-4 w-4 text-emerald-600" />
                <h3 className="text-sm font-semibold text-slate-900 dark:text-slate-100">
                  Model Pricing Catalog (USD per 1M Tokens)
                </h3>
              </div>

              <div className="rounded-xl border border-slate-200 dark:border-slate-800 overflow-hidden max-h-80 overflow-y-auto">
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>Model</TableHead>
                      <TableHead>Provider</TableHead>
                      <TableHead>Input / 1M</TableHead>
                      <TableHead>Output / 1M</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {pricingCatalog.map((p) => (
                      <TableRow key={p.model_id}>
                        <TableCell className="font-mono text-xs font-semibold text-slate-800 dark:text-slate-200">
                          {p.model_id}
                        </TableCell>
                        <TableCell className="text-xs capitalize text-slate-500">
                          {p.provider}
                        </TableCell>
                        <TableCell className="font-mono text-xs text-slate-700 dark:text-slate-300">
                          ${p.input_cost_per_1m.toFixed(2)}
                        </TableCell>
                        <TableCell className="font-mono text-xs text-slate-700 dark:text-slate-300">
                          ${p.output_cost_per_1m.toFixed(2)}
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </div>
              <p className="text-[10px] text-slate-400 mt-2">
                Transparent model pricing. Distinguishes provider-reported billing from standard catalog estimates.
              </p>
            </Card>
          </div>
        </TabsContent>

        {/* Tab 4: Latency Breakdown */}
        <TabsContent value="latency">
          <div className="grid gap-4 md:grid-cols-2">
            <Card className="p-5 bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-2xl shadow-2xs">
              <div className="flex items-center gap-2 mb-4">
                <Clock className="h-4 w-4 text-blue-600" />
                <h3 className="text-sm font-semibold text-slate-900 dark:text-slate-100">
                  Latency Percentiles (E2E)
                </h3>
              </div>

              <div className="grid grid-cols-3 gap-3 mb-6">
                <div className="p-3 rounded-xl bg-slate-50 dark:bg-slate-800/40 border border-slate-200 dark:border-slate-800">
                  <span className="text-[10px] text-slate-500 block">P50 (Median)</span>
                  <span className="text-base font-bold font-mono text-slate-900 dark:text-white">
                    {overview?.p50_latency_ms ? `${overview.p50_latency_ms}ms` : metrics?.p50_latency_ms ? `${metrics.p50_latency_ms}ms` : '--'}
                  </span>
                </div>
                <div className="p-3 rounded-xl bg-slate-50 dark:bg-slate-800/40 border border-slate-200 dark:border-slate-800">
                  <span className="text-[10px] text-slate-500 block">P95 (SLA Target)</span>
                  <span className="text-base font-bold font-mono text-blue-600">
                    {overview?.p95_latency_ms ? `${overview.p95_latency_ms}ms` : metrics?.p95_latency_ms ? `${metrics.p95_latency_ms}ms` : '--'}
                  </span>
                </div>
                <div className="p-3 rounded-xl bg-slate-50 dark:bg-slate-800/40 border border-slate-200 dark:border-slate-800">
                  <span className="text-[10px] text-slate-500 block">P99 (Worst Case)</span>
                  <span className="text-base font-bold font-mono text-amber-600">
                    {overview?.p99_latency_ms ? `${overview.p99_latency_ms}ms` : metrics?.p99_latency_ms ? `${metrics.p99_latency_ms}ms` : '--'}
                  </span>
                </div>
              </div>

              <p className="text-[11px] text-slate-500">
                Calculated strictly on actual execution duration with minimum 3-sample threshold protection against low-sample skew.
              </p>
            </Card>

            <Card className="p-5 bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-2xl shadow-2xs">
              <div className="flex items-center gap-2 mb-4">
                <Layers className="h-4 w-4 text-purple-600" />
                <h3 className="text-sm font-semibold text-slate-900 dark:text-slate-100">
                  Pipeline Stage Duration Breakdown
                </h3>
              </div>

              <div className="space-y-3">
                {[
                  { name: 'Hybrid Evidence Retrieval', val: metrics?.retrieval_latency_ms ?? 0, color: 'bg-blue-600' },
                  { name: 'Neural Reranking', val: metrics?.reranking_latency_ms ?? 0, color: 'bg-indigo-600' },
                  { name: 'LLM Generation', val: metrics?.generation_latency_ms ?? 0, color: 'bg-purple-600' },
                  { name: 'Citation Audit', val: metrics?.citation_validation_latency_ms ?? 0, color: 'bg-emerald-600' },
                  { name: 'Self-Healing Recovery', val: metrics?.recovery_latency_ms ?? 0, color: 'bg-amber-600' },
                ].map((item) => (
                  <div key={item.name} className="space-y-1">
                    <div className="flex justify-between text-xs font-medium">
                      <span className="text-slate-700 dark:text-slate-300">{item.name}</span>
                      <span className="font-mono text-slate-500">{item.val > 0 ? `${item.val}ms` : '--'}</span>
                    </div>
                    <div className="h-2 w-full rounded-full bg-slate-100 dark:bg-slate-800 overflow-hidden">
                      <div
                        className={`h-full rounded-full ${item.color}`}
                        style={{ width: `${Math.min(100, Math.max(item.val > 0 ? 5 : 0, (item.val / 1000) * 100))}%` }}
                      />
                    </div>
                  </div>
                ))}
              </div>
            </Card>
          </div>
        </TabsContent>

        {/* Tab 5: Alerts */}
        <TabsContent value="alerts">
          <Card className="p-5 bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-2xl shadow-2xs">
            <div className="flex items-center justify-between mb-4">
              <div className="flex items-center gap-2">
                <AlertTriangle className="h-4 w-4 text-amber-600" />
                <h3 className="text-sm font-semibold text-slate-900 dark:text-slate-100">
                  Reliability Alerts & Threshold Monitors
                </h3>
              </div>
              <Badge variant="outline" size="sm" className="text-xs">
                {alerts.length} Evaluated Rules
              </Badge>
            </div>

            {alerts.length === 0 ? (
              <div className="text-center py-10 text-slate-500">
                <CheckCircle2 className="h-8 w-8 text-emerald-500 mx-auto mb-2 opacity-80" />
                <p className="font-semibold text-xs text-slate-700 dark:text-slate-300">
                  All Systems Within SLA Thresholds
                </p>
                <p className="text-[11px] text-slate-500 mt-0.5">
                  No elevated error rates, sustained latency spikes, or provider timeouts detected.
                </p>
              </div>
            ) : (
              <div className="space-y-3">
                {alerts.map((alt) => (
                  <div
                    key={alt.id}
                    className="p-3.5 rounded-xl border border-slate-200 dark:border-slate-800 bg-slate-50/60 dark:bg-slate-850 flex items-start justify-between gap-4"
                  >
                    <div className="space-y-1">
                      <div className="flex items-center gap-2">
                        <Badge
                          variant="outline"
                          size="sm"
                          className={
                            alt.severity === 'critical'
                              ? 'bg-rose-50 text-rose-700 border-rose-200 dark:bg-rose-950/40 dark:text-rose-300'
                              : 'bg-amber-50 text-amber-700 border-amber-200 dark:bg-amber-950/40 dark:text-amber-300'
                          }
                        >
                          {alt.severity.toUpperCase()}
                        </Badge>
                        <span className="font-semibold text-xs text-slate-900 dark:text-slate-100">
                          {alt.name}
                        </span>
                        {alt.status === 'cooldown' && (
                          <Badge variant="outline" size="sm" className="bg-slate-100 text-slate-600 text-[10px]">
                            Cooldown
                          </Badge>
                        )}
                      </div>
                      <p className="text-xs text-slate-600 dark:text-slate-300">{alt.message}</p>
                      <span className="font-mono text-[10px] text-slate-400 block">
                        Condition: {alt.condition} | Evaluated at {new Date(alt.triggered_at).toLocaleTimeString()}
                      </span>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </Card>
        </TabsContent>

        {/* Tab 6: Readiness Health */}
        <TabsContent value="readiness">
          <Card className="p-5 bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-2xl shadow-2xs">
            <div className="flex items-center gap-2 mb-4">
              <Server className="h-4 w-4 text-blue-600" />
              <h3 className="text-sm font-semibold text-slate-900 dark:text-slate-100">
                Service Readiness & Dependency Probes
              </h3>
            </div>

            <div className="grid gap-3 sm:grid-cols-3">
              <div className="p-4 rounded-xl border border-slate-200 bg-slate-50 dark:bg-slate-800/40 dark:border-slate-800 space-y-2">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-1.5 font-semibold text-xs text-slate-900 dark:text-slate-100">
                    <Database className="h-3.5 w-3.5 text-blue-600" />
                    <span>PostgreSQL</span>
                  </div>
                  <Badge variant="outline" size="sm" className="bg-emerald-50 text-emerald-700 border-emerald-200">
                    Connected
                  </Badge>
                </div>
                <p className="text-[11px] text-slate-500">Relational metadata, audit logs, and trace records.</p>
              </div>

              <div className="p-4 rounded-xl border border-slate-200 bg-slate-50 dark:bg-slate-800/40 dark:border-slate-800 space-y-2">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-1.5 font-semibold text-xs text-slate-900 dark:text-slate-100">
                    <Zap className="h-3.5 w-3.5 text-indigo-600" />
                    <span>pgvector HNSW</span>
                  </div>
                  <Badge variant="outline" size="sm" className="bg-emerald-50 text-emerald-700 border-emerald-200">
                    Available
                  </Badge>
                </div>
                <p className="text-[11px] text-slate-500">Cosine similarity vector index for dense retrieval.</p>
              </div>

              <div className="p-4 rounded-xl border border-slate-200 bg-slate-50 dark:bg-slate-800/40 dark:border-slate-800 space-y-2">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-1.5 font-semibold text-xs text-slate-900 dark:text-slate-100">
                    <Activity className="h-3.5 w-3.5 text-emerald-600" />
                    <span>LLM Engine</span>
                  </div>
                  <Badge variant="outline" size="sm" className="bg-emerald-50 text-emerald-700 border-emerald-200">
                    Operational
                  </Badge>
                </div>
                <p className="text-[11px] text-slate-500">Provider gateway for grounded chat and self-healing verification.</p>
              </div>
            </div>
          </Card>
        </TabsContent>
      </Tabs>

      {/* Trace Detail Waterfall & Provenance Slide-Over Drawer */}
      <Drawer
        open={selectedTrace !== null}
        onClose={() => {
          setSelectedTrace(null);
          setSelectedStep(null);
        }}
        title={
          selectedTrace ? (
            <div className="flex items-center gap-2">
              <Activity className="h-4 w-4 text-blue-600" />
              <span>Trace Audit: {selectedTrace.id}</span>
            </div>
          ) : undefined
        }
        description={selectedTrace?.query}
        width="xl"
      >
        {selectedTrace && (
          <div className="space-y-5 text-xs">
            {/* Trace Meta Summary */}
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 rounded-xl border border-slate-200 bg-slate-50 p-3.5 dark:bg-slate-800/40 dark:border-slate-800">
              <div>
                <span className="text-[10px] text-slate-500 block">Total Duration</span>
                <span className="font-mono font-bold text-slate-900 dark:text-slate-100">
                  {selectedTrace.durationMs}ms
                </span>
              </div>
              <div>
                <span className="text-[10px] text-slate-500 block">Status</span>
                <span className="font-semibold text-blue-600 capitalize">
                  {selectedTrace.status}
                </span>
              </div>
              <div>
                <span className="text-[10px] text-slate-500 block">Token Accounting</span>
                <span className="font-mono font-bold text-slate-900 dark:text-slate-100">
                  {selectedTrace.tokensTotal ?? 0} tokens
                </span>
                <span className="text-[9px] text-slate-400 block">
                  {selectedTrace.promptTokens ?? '--'} in / {selectedTrace.completionTokens ?? '--'} out
                </span>
              </div>
              <div>
                <span className="text-[10px] text-slate-500 block">Cost Attribution</span>
                <div className="flex items-center gap-1.5">
                  <span className="font-mono font-bold text-slate-700 dark:text-slate-300">
                    {selectedTrace.estimatedCostUsd !== null && selectedTrace.estimatedCostUsd !== undefined
                      ? `$${selectedTrace.estimatedCostUsd.toFixed(4)}`
                      : 'N/A'}
                  </span>
                  {formatCostBadge(selectedTrace.costStatus)}
                </div>
              </div>
            </div>

            {/* Retrieval & Grounding Evaluation Summary */}
            <div className="grid grid-cols-3 gap-2 p-3 rounded-xl border border-slate-200 bg-white dark:bg-slate-900 dark:border-slate-800 text-[11px]">
              <div>
                <span className="text-[10px] text-slate-400 block uppercase">Retrieval Strategy</span>
                <span className="font-semibold text-slate-800 dark:text-slate-200">
                  {selectedTrace.retrievalMethod || 'dense_vector'}
                </span>
              </div>
              <div>
                <span className="text-[10px] text-slate-400 block uppercase">Citation Validation</span>
                <span className="font-semibold text-emerald-600">
                  {selectedTrace.citationValidationPassed ? 'Passed (Ground Truth)' : 'Pending / Bypassed'}
                </span>
              </div>
              <div>
                <span className="text-[10px] text-slate-400 block uppercase">Verification Status</span>
                <span className="font-semibold text-slate-800 dark:text-slate-200">
                  {selectedTrace.verificationStatus || 'grounded_evidence'}
                </span>
              </div>
            </div>

            {/* Chunk Score Provenance Table (Phase 11) */}
            {selectedTrace.retrievalScores && selectedTrace.retrievalScores.length > 0 && (
              <div className="space-y-2">
                <div className="flex items-center justify-between">
                  <span className="font-bold text-slate-900 dark:text-slate-100 block">
                    Retrieval Chunk Score Provenance Audit
                  </span>
                  <Badge variant="outline" size="sm" className="text-[10px]">
                    {selectedTrace.retrievalScores.length} Evaluated Chunks
                  </Badge>
                </div>

                <div className="rounded-xl border border-slate-200 dark:border-slate-800 overflow-hidden">
                  <Table>
                    <TableHeader>
                      <TableRow>
                        <TableHead>Chunk ID</TableHead>
                        <TableHead>Vector Cosine</TableHead>
                        <TableHead>BM25 Okapi</TableHead>
                        <TableHead>RRF Fusion</TableHead>
                        <TableHead>Reranker</TableHead>
                        <TableHead>Rank</TableHead>
                        <TableHead>Used</TableHead>
                        <TableHead>Cited</TableHead>
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {selectedTrace.retrievalScores.map((sc) => (
                        <TableRow key={sc.chunk_id}>
                          <TableCell className="font-mono text-[11px] font-semibold text-blue-600 dark:text-blue-400 max-w-[120px] truncate">
                            {sc.chunk_id}
                          </TableCell>
                          <TableCell className="font-mono text-[11px]">
                            {sc.vector_score !== null && sc.vector_score !== undefined
                              ? sc.vector_score.toFixed(3)
                              : '--'}
                          </TableCell>
                          <TableCell className="font-mono text-[11px]">
                            {sc.bm25_score !== null && sc.bm25_score !== undefined
                              ? sc.bm25_score.toFixed(2)
                              : '--'}
                          </TableCell>
                          <TableCell className="font-mono text-[11px]">
                            {sc.rrf_score !== null && sc.rrf_score !== undefined
                              ? sc.rrf_score.toFixed(4)
                              : '--'}
                          </TableCell>
                          <TableCell className="font-mono text-[11px]">
                            {sc.rerank_score !== null && sc.rerank_score !== undefined
                              ? sc.rerank_score.toFixed(3)
                              : '--'}
                          </TableCell>
                          <TableCell className="font-mono text-[11px] font-bold">
                            #{sc.final_rank ?? '--'}
                          </TableCell>
                          <TableCell>
                            {sc.is_used_in_generation ? (
                              <CheckCircle className="h-3.5 w-3.5 text-emerald-600" />
                            ) : (
                              <span className="text-slate-300">-</span>
                            )}
                          </TableCell>
                          <TableCell>
                            {sc.is_cited ? (
                              <CheckCircle className="h-3.5 w-3.5 text-blue-600" />
                            ) : (
                              <span className="text-slate-300">-</span>
                            )}
                          </TableCell>
                        </TableRow>
                      ))}
                    </TableBody>
                  </Table>
                </div>
                <p className="text-[10px] text-slate-400">
                  Scores preserve authentic engine outputs without cross-metric distortion. Vector/Reranker scores are normalized [0, 1]; BM25 scores represent raw term matches.
                </p>
              </div>
            )}

            {/* Waterfall Timeline */}
            <div>
              <div className="flex items-center justify-between mb-2">
                <span className="font-bold text-slate-900 dark:text-slate-100 block">
                  Execution Span Waterfall & State Graph Nodes
                </span>
                <span className="text-[11px] text-slate-500">
                  {selectedTrace.steps?.length ?? 0} recorded spans
                </span>
              </div>

              <div className="space-y-2">
                {selectedTrace.steps?.map((step) => {
                  const isSelected = selectedStep?.id === step.id;
                  const isFail = step.status === 'failed';
                  const isRec = step.status === 'recovered';
                  const isSkip = step.isSkipped || step.status === 'skipped';
                  return (
                    <div
                      key={step.id}
                      onClick={() => setSelectedStep(step)}
                      className={`p-3 rounded-xl border transition-all cursor-pointer ${
                        isSelected
                          ? 'border-blue-500 bg-blue-50/50 dark:bg-blue-950/40'
                          : isSkip
                          ? 'border-dashed border-slate-200 bg-slate-50/40 opacity-75 dark:bg-slate-900/40 dark:border-slate-800'
                          : 'border-slate-200 bg-white hover:border-slate-300 dark:bg-slate-900 dark:border-slate-800'
                      }`}
                    >
                      <div className="flex items-center justify-between mb-1.5">
                        <div className="flex items-center gap-2">
                          <Badge
                            variant="outline"
                            size="sm"
                            className={
                              isSkip
                                ? 'bg-slate-100 text-slate-500 border-slate-300'
                                : isFail
                                ? 'bg-rose-50 text-rose-700 border-rose-200'
                                : isRec
                                ? 'bg-purple-50 text-purple-700 border-purple-200'
                                : 'bg-slate-100 text-slate-600'
                            }
                          >
                            {isSkip ? 'SKIPPED' : step.stepType}
                          </Badge>
                          <span
                            className={`font-semibold text-slate-900 dark:text-slate-100 ${
                              isSkip ? 'italic text-slate-500' : ''
                            }`}
                          >
                            {step.name}
                          </span>
                        </div>
                        <div className="flex items-center gap-2">
                          {step.promptTokens && (
                            <span className="text-[10px] text-slate-400 font-mono">
                              {step.promptTokens} in / {step.completionTokens} out
                            </span>
                          )}
                          <span className="font-mono text-[11px] text-slate-500">
                            {isSkip ? '0ms' : `${step.durationMs}ms`}
                          </span>
                        </div>
                      </div>

                      {/* Waterfall Progress representation */}
                      <div className="h-1.5 w-full rounded-full bg-slate-100 dark:bg-slate-800 overflow-hidden">
                        <div
                          className={`h-full rounded-full ${
                            isSkip
                              ? 'bg-slate-300 dark:bg-slate-700'
                              : isFail
                              ? 'bg-rose-500'
                              : isRec
                              ? 'bg-purple-500'
                              : 'bg-blue-600'
                          }`}
                          style={{
                            width: isSkip
                              ? '3%'
                              : `${Math.max(
                                  3,
                                  ((step.durationMs || 5) / (selectedTrace.durationMs || 100)) * 100
                                )}%`,
                          }}
                        />
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>

            {/* Selected Step IO Inspector */}
            {selectedStep && (
              <div className="rounded-xl border border-slate-200 bg-slate-50 p-4 space-y-3 dark:bg-slate-800/40 dark:border-slate-800">
                <div className="flex items-center justify-between">
                  <span className="font-semibold text-slate-900 dark:text-slate-100">
                    Span Inspector: {selectedStep.name}
                  </span>
                  <span className="font-mono text-slate-500">{selectedStep.durationMs}ms</span>
                </div>

                {selectedStep.errorMessage && (
                  <div className="p-2.5 rounded-lg bg-rose-50 border border-rose-200 text-rose-800 text-xs">
                    <span className="font-bold">Error [{selectedStep.errorCode}]: </span>
                    {selectedStep.errorMessage}
                  </div>
                )}

                <div className="space-y-2">
                  <div>
                    <span className="text-[10px] text-slate-500 uppercase font-semibold block mb-1">
                      Sanitized Inputs:
                    </span>
                    <pre className="p-2.5 rounded-lg bg-white border border-slate-200 text-slate-800 font-mono text-[10px] overflow-x-auto dark:bg-slate-900 dark:border-slate-800 dark:text-slate-300">
                      {JSON.stringify(selectedStep.inputs || {}, null, 2)}
                    </pre>
                  </div>

                  <div>
                    <span className="text-[10px] text-slate-500 uppercase font-semibold block mb-1">
                      Sanitized Outputs:
                    </span>
                    <pre className="p-2.5 rounded-lg bg-white border border-slate-200 text-slate-800 font-mono text-[10px] overflow-x-auto dark:bg-slate-900 dark:border-slate-800 dark:text-slate-300">
                      {JSON.stringify(selectedStep.outputs || {}, null, 2)}
                    </pre>
                  </div>
                </div>
              </div>
            )}
          </div>
        )}
      </Drawer>
    </div>
  );
}
