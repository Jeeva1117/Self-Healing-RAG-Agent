import { useState, useEffect } from 'react';
import {
  CheckCircle2,
  FileCheck,
  AlertTriangle,
  Play,
  Layers,
  Database,
  RefreshCw,
  Clock,
  ShieldCheck,
  ChevronRight,
  TrendingUp,
  TrendingDown,
  XCircle,
  Eye,
} from 'lucide-react';
import { Card } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { MetricCard } from '@/components/ui/metric-card';
import { Tabs, TabsList, TabsTrigger, TabsContent } from '@/components/ui/tabs';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { useToast } from '@/context/ToastContext';
import { evaluationService } from '@/services/evaluationService';
import type {
  BaselineComparison,
  EvaluationDatasetItem,
  EvaluationRunDetailResponse,
  EvaluationRunListItem,
  EvaluationSummaryStats,
} from '@/types/evaluation';

export function EvaluationPage() {
  const { toast } = useToast();
  const [isRunning, setIsRunning] = useState(false);
  const [isLoading, setIsLoading] = useState(true);
  const [summaryStats, setSummaryStats] = useState<EvaluationSummaryStats | null>(null);
  const [runs, setRuns] = useState<EvaluationRunListItem[]>([]);
  const [datasets, setDatasets] = useState<EvaluationDatasetItem[]>([]);
  const [selectedRun, setSelectedRun] = useState<EvaluationRunDetailResponse | null>(null);
  const [comparison, setComparison] = useState<BaselineComparison | null>(null);

  const loadData = async () => {
    try {
      setIsLoading(true);
      const [statsData, runsData, datasetsData] = await Promise.all([
        evaluationService.getSummaryStats().catch(() => null),
        evaluationService.listRuns().catch(() => []),
        evaluationService.listDatasets().catch(() => []),
      ]);
      setSummaryStats(statsData);
      setRuns(runsData);
      setDatasets(datasetsData);

      if (runsData.length > 0 && !selectedRun) {
        const firstRun = await evaluationService.getRun(runsData[0].id).catch(() => null);
        setSelectedRun(firstRun);
      }
    } catch (err) {
      console.error('Failed to load evaluation data', err);
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    loadData();
  }, []);

  const handleTriggerRun = async () => {
    try {
      setIsRunning(true);
      toast.info('Starting evaluation benchmark across all test categories...');
      const newRun = await evaluationService.triggerRun({
        name: `Benchmark Run ${new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}`,
        dataset_name: 'enterprise_rag_eval_v1',
        dataset_version: '1.0.0',
      });
      toast.success(`Evaluation complete: ${newRun.passed_cases}/${newRun.total_cases} passed (${(newRun.pass_rate * 100).toFixed(1)}%)`);
      setSelectedRun(newRun);
      await loadData();
    } catch (err: any) {
      toast.error(err.message || 'Failed to execute evaluation run');
    } finally {
      setIsRunning(false);
    }
  };

  const handleSelectRun = async (runId: string) => {
    try {
      const runDetail = await evaluationService.getRun(runId);
      setSelectedRun(runDetail);

      // If there is another run, calculate comparison diff
      const otherRuns = runs.filter((r) => r.id !== runId);
      if (otherRuns.length > 0) {
        const comp = await evaluationService.compareRuns(runId, otherRuns[0].id).catch(() => null);
        setComparison(comp);
      } else {
        setComparison(null);
      }
    } catch (err: any) {
      toast.error(err?.message || 'Failed to fetch run details');
    }
  };

  const hasRuns = runs.length > 0;

  return (
    <div className="space-y-6">
      {/* Page Header */}
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <div className="flex items-center gap-2">
            <h1 className="text-2xl font-bold tracking-tight text-slate-900 dark:text-white">
              RAG Evaluation & Quality Intelligence Engine
            </h1>
            <span className="inline-flex items-center px-2 py-0.5 rounded-full text-[11px] font-semibold bg-emerald-100 text-emerald-800 dark:bg-emerald-950/60 dark:text-emerald-400">
              Evaluation Engine Active
            </span>
          </div>
          <p className="text-xs sm:text-sm text-slate-500 dark:text-slate-400 mt-1">
            Deterministic quality intelligence measuring hybrid retrieval precision, evidence grounding, citation fidelity, and self-healing recovery.
          </p>
        </div>

        <div className="flex items-center gap-2">
          <Button
            size="sm"
            variant="outline"
            onClick={loadData}
            disabled={isLoading || isRunning}
            className="gap-1.5"
          >
            <RefreshCw className={`h-3.5 w-3.5 ${isLoading ? 'animate-spin' : ''}`} />
            <span>Refresh</span>
          </Button>
          <Button
            size="sm"
            onClick={handleTriggerRun}
            disabled={isRunning}
            className="gap-1.5 bg-blue-600 hover:bg-blue-700 text-white font-medium shadow-sm shadow-blue-500/20"
          >
            {isRunning ? (
              <RefreshCw className="h-3.5 w-3.5 animate-spin" />
            ) : (
              <Play className="h-3.5 w-3.5" />
            )}
            <span>{isRunning ? 'Evaluating Testbed...' : 'Trigger Benchmark Run'}</span>
          </Button>
        </div>
      </div>

      {/* Top 5 Evaluation Metrics Cards */}
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-5">
        <MetricCard
          title="Faithfulness & Grounding"
          value={
            summaryStats && summaryStats.total_runs > 0 && summaryStats.average_groundedness > 0
              ? `${(summaryStats.average_groundedness * 100).toFixed(1)}%`
              : '--'
          }
          subtitle="Lexical evidence fidelity"
          icon={FileCheck}
          badge={hasRuns ? 'Measured' : 'Awaiting Run'}
          badgeVariant={hasRuns ? 'success' : 'secondary'}
        />
        <MetricCard
          title="Context Precision@5"
          value={
            summaryStats && summaryStats.total_runs > 0 && summaryStats.average_precision_at_5 > 0
              ? `${(summaryStats.average_precision_at_5 * 100).toFixed(1)}%`
              : '--'
          }
          subtitle="Signal-to-noise ratio"
          icon={Layers}
          badge={hasRuns ? 'Measured' : 'Awaiting Run'}
          badgeVariant={hasRuns ? 'success' : 'secondary'}
        />
        <MetricCard
          title="Context Recall@5"
          value={
            summaryStats && summaryStats.total_runs > 0 && summaryStats.average_recall_at_5 > 0
              ? `${(summaryStats.average_recall_at_5 * 100).toFixed(1)}%`
              : '--'
          }
          subtitle="Expected chunk recall"
          icon={Database}
          badge={hasRuns ? 'Measured' : 'Awaiting Run'}
          badgeVariant={hasRuns ? 'success' : 'secondary'}
        />
        <MetricCard
          title="Mean Reciprocal Rank"
          value={
            summaryStats && summaryStats.total_runs > 0 && summaryStats.average_mrr > 0
              ? summaryStats.average_mrr.toFixed(3)
              : '--'
          }
          subtitle="Rank of first relevant chunk"
          icon={CheckCircle2}
          badge={hasRuns ? 'Measured' : 'Awaiting Run'}
          badgeVariant={hasRuns ? 'success' : 'secondary'}
        />
        <MetricCard
          title="Recovery Success Rate"
          value={
            summaryStats && summaryStats.total_runs > 0 && summaryStats.recovery_success_rate > 0
              ? `${(summaryStats.recovery_success_rate * 100).toFixed(1)}%`
              : '--'
          }
          subtitle="Self-healing resolution rate"
          icon={ShieldCheck}
          badge={hasRuns ? 'Measured' : 'Awaiting Run'}
          badgeVariant={hasRuns ? 'success' : 'secondary'}
        />
      </div>

      {/* Main Content Tabs */}
      <Tabs defaultValue="overview">
        <div className="flex items-center justify-between mb-3">
          <TabsList className="bg-slate-100 p-1 dark:bg-slate-800">
            <TabsTrigger value="overview">Quality Overview</TabsTrigger>
            <TabsTrigger value="runs">Evaluation Runs ({runs.length})</TabsTrigger>
            <TabsTrigger value="datasets">Test Datasets ({datasets.length})</TabsTrigger>
            <TabsTrigger value="failures">
              Failure Analysis (
              {selectedRun ? selectedRun.case_results.filter((c) => !c.passed).length : 0}
              )
            </TabsTrigger>
          </TabsList>
          <span className="text-[11px] font-mono text-slate-500">
            Deterministic Evaluation Suite v1.0
          </span>
        </div>

        {/* Tab 1: Quality Overview */}
        <TabsContent value="overview">
          {selectedRun ? (
            <div className="space-y-6">
              {/* Selected Run Banner */}
              <div className="rounded-2xl border border-slate-200 bg-white p-5 shadow-2xs dark:border-slate-800 dark:bg-slate-900">
                <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
                  <div>
                    <div className="flex items-center gap-2">
                      <h3 className="font-semibold text-slate-900 dark:text-white text-base">
                        {selectedRun.name}
                      </h3>
                      <span className="px-2 py-0.5 rounded text-xs font-mono font-medium bg-blue-50 text-blue-700 dark:bg-blue-950 dark:text-blue-400">
                        {selectedRun.dataset_name} v{selectedRun.dataset_version}
                      </span>
                    </div>
                    <div className="flex items-center gap-4 text-xs text-slate-500 mt-2">
                      <span className="flex items-center gap-1">
                        <Clock className="h-3.5 w-3.5" />
                        {new Date(selectedRun.created_at).toLocaleString()}
                      </span>
                      <span>Total Cases: {selectedRun.total_cases}</span>
                      <span className="text-emerald-600 font-medium">Passed: {selectedRun.passed_cases}</span>
                      <span className="text-rose-600 font-medium">Failed: {selectedRun.failed_cases}</span>
                    </div>
                  </div>

                  <div className="text-right">
                    <div className="text-2xl font-bold font-mono text-slate-900 dark:text-white">
                      {(selectedRun.pass_rate * 100).toFixed(1)}%
                    </div>
                    <span className="text-xs text-slate-500 font-medium">Benchmark Pass Rate</span>
                  </div>
                </div>

                {/* Regression Comparison Pill if available */}
                {comparison && comparison.is_compatible && (
                  <div className="mt-4 pt-4 border-t border-slate-100 dark:border-slate-800 flex flex-wrap items-center gap-3 text-xs">
                    <span className="font-semibold text-slate-700 dark:text-slate-300">
                      Delta vs Prior Baseline:
                    </span>
                    {Object.entries(comparison.improvements).map(([metric, delta]) => (
                      <span key={metric} className="inline-flex items-center gap-1 text-emerald-600 font-medium bg-emerald-50 dark:bg-emerald-950/60 px-2 py-0.5 rounded">
                        <TrendingUp className="h-3 w-3" />
                        {metric}: +{(delta * 100).toFixed(1)}%
                      </span>
                    ))}
                    {Object.entries(comparison.regressions).map(([metric, delta]) => (
                      <span key={metric} className="inline-flex items-center gap-1 text-rose-600 font-medium bg-rose-50 dark:bg-rose-950/60 px-2 py-0.5 rounded">
                        <TrendingDown className="h-3 w-3" />
                        {metric}: {(delta * 100).toFixed(1)}%
                      </span>
                    ))}
                    {Object.keys(comparison.improvements).length === 0 && Object.keys(comparison.regressions).length === 0 && (
                      <span className="text-slate-500">All key metrics stable within ±2%.</span>
                    )}
                  </div>
                )}
              </div>

              {/* Case Results Table */}
              <div className="rounded-2xl border border-slate-200 bg-white overflow-hidden shadow-2xs dark:border-slate-800 dark:bg-slate-900">
                <div className="p-4 border-b border-slate-200 dark:border-slate-800 bg-slate-50/50 dark:bg-slate-900/50">
                  <h4 className="text-xs font-semibold text-slate-700 dark:text-slate-300 uppercase tracking-wider">
                    Test Case Execution Matrix
                  </h4>
                </div>
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>Case ID</TableHead>
                      <TableHead>Category</TableHead>
                      <TableHead>Query</TableHead>
                      <TableHead>Status</TableHead>
                      <TableHead>Groundedness</TableHead>
                      <TableHead>Citation Validity</TableHead>
                      <TableHead>Latency</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {selectedRun.case_results.map((c) => (
                      <TableRow key={c.test_case_id}>
                        <TableCell className="font-mono text-xs font-semibold text-slate-900 dark:text-white">
                          {c.test_case_id}
                        </TableCell>
                        <TableCell>
                          <span className="inline-flex items-center px-2 py-0.5 rounded text-[11px] font-mono bg-slate-100 text-slate-700 dark:bg-slate-800 dark:text-slate-300">
                            {c.category}
                          </span>
                        </TableCell>
                        <TableCell className="text-xs text-slate-700 dark:text-slate-300 max-w-xs truncate" title={c.query}>
                          {c.query}
                        </TableCell>
                        <TableCell>
                          {c.passed ? (
                            <span className="inline-flex items-center gap-1 text-emerald-600 font-medium text-xs">
                              <CheckCircle2 className="h-3.5 w-3.5" />
                              Passed
                            </span>
                          ) : (
                            <span className="inline-flex items-center gap-1 text-rose-600 font-medium text-xs">
                              <XCircle className="h-3.5 w-3.5" />
                              Failed
                            </span>
                          )}
                        </TableCell>
                        <TableCell className="font-mono text-xs text-slate-600 dark:text-slate-400">
                          {(c.answer_metrics.groundedness_score * 100).toFixed(0)}%
                        </TableCell>
                        <TableCell className="font-mono text-xs text-slate-600 dark:text-slate-400">
                          {(c.answer_metrics.citation_validity_score * 100).toFixed(0)}%
                        </TableCell>
                        <TableCell className="font-mono text-xs text-slate-500">
                          {c.total_latency_ms.toFixed(0)}ms
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </div>
            </div>
          ) : (
            <Card className="p-12 text-center border-dashed border-slate-200 bg-white rounded-2xl shadow-2xs dark:bg-slate-900/40 dark:border-slate-800">
              <div className="flex h-12 w-12 items-center justify-center rounded-2xl bg-blue-50 text-blue-600 mx-auto mb-3 dark:bg-blue-900/30">
                <Play className="h-6 w-6" />
              </div>
              <h3 className="text-sm font-semibold text-slate-900 dark:text-slate-100">
                No Automated Evaluation Runs Executed Yet
              </h3>
              <p className="text-xs text-slate-500 max-w-md mx-auto mt-1 mb-4 leading-relaxed">
                Click below to trigger the benchmark suite against your active hybrid retrieval, LangGraph orchestrator, and self-healing recovery engine.
              </p>
              <Button
                size="sm"
                onClick={handleTriggerRun}
                disabled={isRunning}
                className="bg-blue-600 hover:bg-blue-700 text-white font-medium"
              >
                {isRunning ? 'Running Benchmark...' : 'Run Benchmark Now'}
              </Button>
            </Card>
          )}
        </TabsContent>

        {/* Tab 2: Evaluation Runs */}
        <TabsContent value="runs">
          <div className="rounded-2xl border border-slate-200 bg-white overflow-hidden shadow-2xs dark:border-slate-800 dark:bg-slate-900">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Run ID</TableHead>
                  <TableHead>Run Name</TableHead>
                  <TableHead>Dataset</TableHead>
                  <TableHead>Pass Rate</TableHead>
                  <TableHead>Faithfulness</TableHead>
                  <TableHead>Executed At</TableHead>
                  <TableHead className="text-right">Actions</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {runs.length > 0 ? (
                  runs.map((r) => (
                    <TableRow key={r.id}>
                      <TableCell className="font-mono text-xs text-slate-500">
                        {r.id.slice(0, 8)}...
                      </TableCell>
                      <TableCell className="font-medium text-xs text-slate-900 dark:text-white">
                        {r.name}
                      </TableCell>
                      <TableCell className="font-mono text-xs text-slate-600 dark:text-slate-400">
                        {r.dataset_name} (v{r.dataset_version})
                      </TableCell>
                      <TableCell>
                        <span className="font-mono font-semibold text-xs text-slate-900 dark:text-white">
                          {(r.pass_rate * 100).toFixed(1)}%
                        </span>
                        <span className="text-[11px] text-slate-400 ml-1">
                          ({r.passed_cases}/{r.total_cases})
                        </span>
                      </TableCell>
                      <TableCell className="font-mono text-xs text-slate-600 dark:text-slate-400">
                        {r.summary_metrics?.mean_groundedness
                          ? `${(r.summary_metrics.mean_groundedness * 100).toFixed(1)}%`
                          : '--'}
                      </TableCell>
                      <TableCell className="text-xs text-slate-500">
                        {new Date(r.created_at).toLocaleString()}
                      </TableCell>
                      <TableCell className="text-right">
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() => handleSelectRun(r.id)}
                          className="h-8 gap-1 text-xs text-blue-600 hover:text-blue-700 hover:bg-blue-50 dark:hover:bg-blue-950"
                        >
                          <Eye className="h-3.5 w-3.5" />
                          <span>Inspect</span>
                        </Button>
                      </TableCell>
                    </TableRow>
                  ))
                ) : (
                  <TableRow>
                    <TableCell colSpan={7} className="text-center py-10 text-slate-500">
                      No historical evaluation runs recorded. Run a benchmark to view results.
                    </TableCell>
                  </TableRow>
                )}
              </TableBody>
            </Table>
          </div>
        </TabsContent>

        {/* Tab 3: Test Datasets */}
        <TabsContent value="datasets">
          <div className="grid gap-4 md:grid-cols-2">
            {datasets.map((d) => (
              <Card key={`${d.name}-${d.version}`} className="p-5 border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 rounded-2xl shadow-2xs">
                <div className="flex items-start justify-between">
                  <div className="flex items-center gap-2">
                    <Database className="h-5 w-5 text-blue-600" />
                    <h3 className="font-semibold text-slate-900 dark:text-white text-sm">
                      {d.name}
                    </h3>
                  </div>
                  <span className="px-2 py-0.5 rounded text-xs font-mono font-semibold bg-blue-50 text-blue-700 dark:bg-blue-950 dark:text-blue-400">
                    v{d.version}
                  </span>
                </div>
                <p className="text-xs text-slate-500 mt-2 leading-relaxed">
                  {d.description}
                </p>
                <div className="mt-4 pt-3 border-t border-slate-100 dark:border-slate-800 flex items-center justify-between text-xs text-slate-600 dark:text-slate-400">
                  <span>Test Cases: <strong className="font-mono text-slate-900 dark:text-white">{d.case_count}</strong></span>
                  <span className="text-blue-600 font-medium">Categories A through K</span>
                </div>
              </Card>
            ))}
          </div>
        </TabsContent>

        {/* Tab 4: Failure Analysis */}
        <TabsContent value="failures">
          {selectedRun && selectedRun.case_results.filter((c) => !c.passed).length > 0 ? (
            <div className="space-y-4">
              {selectedRun.case_results
                .filter((c) => !c.passed)
                .map((f) => (
                  <Card key={f.test_case_id} className="p-5 border border-rose-200 dark:border-rose-950 bg-rose-50/20 dark:bg-rose-950/20 rounded-2xl shadow-2xs">
                    <div className="flex items-start justify-between">
                      <div className="flex items-center gap-2">
                        <AlertTriangle className="h-4 w-4 text-rose-600" />
                        <span className="font-mono font-bold text-xs text-slate-900 dark:text-white">
                          {f.test_case_id}
                        </span>
                        <span className="px-2 py-0.5 rounded text-[11px] font-mono bg-rose-100 text-rose-800 dark:bg-rose-900 dark:text-rose-300">
                          {f.category}
                        </span>
                      </div>
                      <span className="text-xs font-mono text-slate-500">
                        {f.total_latency_ms.toFixed(0)}ms
                      </span>
                    </div>

                    <div className="mt-3">
                      <span className="text-xs text-slate-500 font-medium">Query:</span>
                      <p className="text-xs font-semibold text-slate-800 dark:text-slate-200 mt-0.5">
                        {f.query}
                      </p>
                    </div>

                    <div className="mt-3 pt-3 border-t border-rose-200/60 dark:border-rose-900/60">
                      <span className="text-xs font-semibold text-rose-700 dark:text-rose-400">
                        Failure Explanations:
                      </span>
                      <ul className="mt-1 space-y-1">
                        {f.failure_reasons.map((r, i) => (
                          <li key={i} className="text-xs text-rose-600 dark:text-rose-300 flex items-start gap-1.5">
                            <ChevronRight className="h-3 w-3 mt-0.5 shrink-0" />
                            <span>{r}</span>
                          </li>
                        ))}
                      </ul>
                    </div>
                  </Card>
                ))}
            </div>
          ) : (
            <Card className="p-10 text-center border-dashed border-slate-200 bg-white rounded-2xl shadow-2xs dark:bg-slate-900/40 dark:border-slate-800">
              <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-emerald-50 text-emerald-600 mx-auto mb-2 dark:bg-emerald-900/30">
                <CheckCircle2 className="h-5 w-5" />
              </div>
              <h3 className="text-xs font-semibold text-slate-900 dark:text-slate-100">
                Zero Evaluation Failures Logged
              </h3>
              <p className="text-[11px] text-slate-500 max-w-sm mx-auto mt-1">
                All executed test cases in this run met grounding thresholds, fact coverage, and citation validity requirements.
              </p>
            </Card>
          )}
        </TabsContent>
      </Tabs>
    </div>
  );
}
