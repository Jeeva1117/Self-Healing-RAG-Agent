import { useState, useEffect } from 'react';
import {
  Activity,
  AlertCircle,
  AlertTriangle,
  CheckCircle2,
  Clock,
  HelpCircle,
  RefreshCw,
  Wrench,
  Loader2,
} from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { useToast } from '@/context/ToastContext';
import { knowledgeBaseService } from '@/services/knowledgeBaseService';
import type { KnowledgeBaseHealthReport, DocumentHealthReport } from '@/types/knowledgeBase';

interface Props {
  kbId: string;
  onOpenRepair?: (docId: string, action: string) => void;
}

export function KbHealthExplorer({ kbId, onOpenRepair }: Props) {
  const { toast } = useToast();
  const [report, setReport] = useState<KnowledgeBaseHealthReport | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);


  const fetchHealth = async () => {
    setIsLoading(true);
    setError(null);
    try {
      const data = await knowledgeBaseService.getHealth(kbId);
      setReport(data);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Failed to load health report.';
      setError(msg);
      toast.error(msg, 'Health Check Error');
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    if (kbId) {
      fetchHealth();
    }
  }, [kbId]);

  if (isLoading) {
    return (
      <div className="bg-white border border-slate-200 rounded-xl p-16 text-center">
        <Loader2 className="w-8 h-8 text-blue-600 animate-spin mx-auto mb-3" />
        <p className="text-sm text-slate-600">Evaluating knowledge base health and vector integrity...</p>
      </div>
    );
  }

  if (error) {
    return (
      <div className="bg-rose-50 border border-rose-200 rounded-xl p-6 text-center">
        <AlertCircle className="w-8 h-8 text-rose-600 mx-auto mb-2" />
        <h4 className="font-semibold text-rose-900">Health Evaluation Failed</h4>
        <p className="text-sm text-rose-700 mt-1">{error}</p>
        <Button variant="outline" size="sm" onClick={fetchHealth} className="mt-4 bg-white">
          <RefreshCw className="w-3.5 h-3.5 mr-1" /> Retry Audit
        </Button>
      </div>
    );
  }

  if (!report) return null;

  return (
    <div className="space-y-6">
      {/* Top Metric Cards */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
        <div className="bg-white border border-slate-200 rounded-xl p-4 shadow-sm">
          <div className="flex items-center justify-between">
            <span className="text-xs font-medium text-slate-500">Healthy Documents</span>
            <CheckCircle2 className="w-4 h-4 text-emerald-500" />
          </div>
          <span className="text-2xl font-bold text-emerald-600 mt-1 block">
            {report.healthy_documents}
          </span>
          <span className="text-xs text-slate-400">of {report.total_documents} total</span>
        </div>

        <div className="bg-white border border-slate-200 rounded-xl p-4 shadow-sm">
          <div className="flex items-center justify-between">
            <span className="text-xs font-medium text-slate-500">Unhealthy / Attention</span>
            <AlertCircle className="w-4 h-4 text-rose-500" />
          </div>
          <span className="text-2xl font-bold text-rose-600 mt-1 block">
            {report.unhealthy_documents}
          </span>
          <span className="text-xs text-slate-400">require remediation</span>
        </div>

        <div className="bg-white border border-slate-200 rounded-xl p-4 shadow-sm">
          <div className="flex items-center justify-between">
            <span className="text-xs font-medium text-slate-500">Stuck in Processing</span>
            <Clock className="w-4 h-4 text-amber-500" />
          </div>
          <span className="text-2xl font-bold text-amber-600 mt-1 block">
            {report.stuck_documents}
          </span>
          <span className="text-xs text-slate-400">&gt; 15 mins stalled</span>
        </div>

        <div className="bg-white border border-slate-200 rounded-xl p-4 shadow-sm">
          <div className="flex items-center justify-between">
            <span className="text-xs font-medium text-slate-500">Missing Embeddings</span>
            <Activity className="w-4 h-4 text-purple-500" />
          </div>
          <span className="text-2xl font-bold text-purple-600 mt-1 block">
            {report.missing_embeddings_count}
          </span>
          <span className="text-xs text-slate-400">across {report.total_chunks} chunks</span>
        </div>
      </div>

      {/* Header & Refresh */}
      <div className="flex items-center justify-between">
        <h3 className="text-base font-semibold text-slate-900">
          Document Health Reports ({report.documents.length})
        </h3>
        <Button variant="outline" size="sm" onClick={fetchHealth} disabled={isLoading}>
          <RefreshCw className={`w-3.5 h-3.5 mr-1.5 ${isLoading ? 'animate-spin' : ''}`} />
          Re-evaluate Health
        </Button>
      </div>

      {/* Document List */}
      <div className="space-y-3">
        {report.documents.map((doc: DocumentHealthReport) => (
          <div
            key={doc.document_id}
            className={`bg-white border rounded-xl p-4 transition-all shadow-sm ${
              doc.is_healthy ? 'border-slate-200' : 'border-rose-200 bg-rose-50/20'
            }`}
          >
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2">
              <div className="flex items-center gap-3">
                {doc.is_healthy ? (
                  <CheckCircle2 className="w-5 h-5 text-emerald-500 shrink-0" />
                ) : (
                  <AlertCircle className="w-5 h-5 text-rose-500 shrink-0" />
                )}
                <div>
                  <h4 className="text-sm font-semibold text-slate-900">{doc.filename}</h4>
                  <div className="flex items-center gap-2 mt-0.5 text-xs text-slate-500">
                    <span>Status: {doc.status}</span>
                    <span>•</span>
                    <span>{doc.chunk_count} chunks</span>
                    <span>•</span>
                    <span>Embedding: {doc.embedding_status}</span>
                    <span>•</span>
                    <span>Active Version: {doc.active_version}</span>
                  </div>
                </div>
              </div>

              <div className="flex items-center gap-2">
                {doc.findings.length === 0 ? (
                  <Badge variant="outline" className="border-emerald-200 text-emerald-700 bg-emerald-50">
                    Healthy
                  </Badge>
                ) : (
                  <Badge variant="destructive">
                    {doc.findings.length} Finding{doc.findings.length > 1 ? 's' : ''}
                  </Badge>
                )}

                {!doc.is_healthy && onOpenRepair && (
                  <Button
                    size="sm"
                    variant="outline"
                    className="border-rose-300 text-rose-700 hover:bg-rose-50 text-xs h-7"
                    onClick={() => {
                      const repairAction = doc.findings.find((f) => f.is_repairable)?.code;
                      const action =
                        repairAction === 'MISSING_EMBEDDINGS'
                          ? 'REPAIR_EMBEDDINGS'
                          : repairAction === 'STALE_PROCESSING'
                          ? 'RECONCILE_STALE'
                          : 'REGENERATE_CHUNKS';
                      onOpenRepair(doc.document_id, action);
                    }}
                  >
                    <Wrench className="w-3 h-3 mr-1" /> Repair Issue
                  </Button>
                )}
              </div>
            </div>

            {/* Findings List */}
            {doc.findings.length > 0 && (
              <div className="mt-3 pt-3 border-t border-slate-100 space-y-2">
                {doc.findings.map((f, idx) => (
                  <div
                    key={idx}
                    className="bg-slate-50 rounded-lg p-2.5 text-xs flex items-start gap-2.5"
                  >
                    {f.severity === 'error' ? (
                      <AlertCircle className="w-4 h-4 text-rose-500 shrink-0 mt-0.5" />
                    ) : f.severity === 'warning' ? (
                      <AlertTriangle className="w-4 h-4 text-amber-500 shrink-0 mt-0.5" />
                    ) : (
                      <HelpCircle className="w-4 h-4 text-blue-500 shrink-0 mt-0.5" />
                    )}
                    <div className="space-y-0.5">
                      <div className="flex items-center gap-2">
                        <span className="font-semibold text-slate-800">{f.title}</span>
                        <code className="text-[10px] bg-slate-200 px-1 py-0.5 rounded text-slate-700">
                          {f.code}
                        </code>
                      </div>
                      <p className="text-slate-600">{f.message}</p>
                      <p className="text-slate-500 font-medium">
                        Remediation: <span className="text-slate-700">{f.remediation}</span>
                      </p>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}
