import React, { useState, useEffect } from 'react';
import {
  Wrench,
  CheckCircle2,
  XCircle,
  Eye,
  RefreshCw,
  Loader2,
} from 'lucide-react';

import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { useToast } from '@/context/ToastContext';
import { knowledgeBaseService } from '@/services/knowledgeBaseService';
import type { DocumentItem, RepairJobResponse, RepairActionRequest } from '@/types/knowledgeBase';

interface Props {
  kbId: string;
  documents: DocumentItem[];
  preselectedDocId?: string | null;
  preselectedAction?: string | null;
  onRepairCompleted?: () => void;
}

export function KbRepairCenter({
  kbId,
  documents,
  preselectedDocId,
  preselectedAction,
  onRepairCompleted,
}: Props) {
  const { toast } = useToast();
  const [jobs, setJobs] = useState<RepairJobResponse[]>([]);
  const [isLoading, setIsLoading] = useState(false);

  // Form State
  const [targetDocId, setTargetDocId] = useState<string>(preselectedDocId || documents[0]?.id || '');
  const [action, setAction] = useState<RepairActionRequest['action']>(
    (preselectedAction as RepairActionRequest['action']) || 'REPAIR_EMBEDDINGS'
  );
  const [dryRun, setDryRun] = useState(false);
  const [isExecuting, setIsExecuting] = useState(false);
  const [activeJobResult, setActiveJobResult] = useState<RepairJobResponse | null>(null);

  const fetchJobs = async () => {
    setIsLoading(true);
    try {
      const data = await knowledgeBaseService.listRepairJobs(kbId);
      setJobs(data);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Failed to load repair jobs.';
      toast.error(msg, 'Repair Jobs Error');
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    if (kbId) {
      fetchJobs();
    }
  }, [kbId]);

  useEffect(() => {
    if (preselectedDocId) setTargetDocId(preselectedDocId);
    if (preselectedAction) setAction(preselectedAction as RepairActionRequest['action']);
  }, [preselectedDocId, preselectedAction]);

  const handleExecute = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!targetDocId) return;

    setIsExecuting(true);
    setActiveJobResult(null);

    try {
      const result = await knowledgeBaseService.repairDocument(kbId, targetDocId, {
        action,
        dry_run: dryRun,
      });
      setActiveJobResult(result);
      if (dryRun) {
        toast.info(`Dry-run simulation completed for ${action}. No data mutated.`, 'Dry-Run Complete');
      } else {
        toast.success(`Repair job completed successfully for ${action}.`, 'Repair Succeeded');
        if (onRepairCompleted) onRepairCompleted();
      }
      await fetchJobs();
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Repair operation failed.';
      toast.error(msg, 'Repair Failed');
    } finally {
      setIsExecuting(false);
    }
  };

  return (
    <div className="space-y-6">
      {/* Targeted Repair Action Form */}
      <div className="bg-white border border-slate-200 rounded-xl p-5 shadow-sm space-y-4">
        <div className="flex items-center gap-2">
          <Wrench className="w-5 h-5 text-blue-600" />
          <h3 className="text-base font-bold text-slate-900">Targeted Document Repair Dispatcher</h3>
        </div>
        <p className="text-xs text-slate-500">
          Execute isolated, non-destructive repair jobs with idempotent locking and postcondition verification.
        </p>

        <form onSubmit={handleExecute} className="grid grid-cols-1 sm:grid-cols-3 gap-3 pt-2">
          <div>
            <label className="text-xs font-semibold text-slate-700 block mb-1">
              Target Document:
            </label>
            <select
              value={targetDocId}
              onChange={(e) => setTargetDocId(e.target.value)}
              className="w-full bg-slate-50 border border-slate-300 rounded-lg px-3 py-2 text-xs font-medium focus:ring-2 focus:ring-blue-500 focus:outline-none"
            >
              {documents.map((d) => (
                <option key={d.id} value={d.id}>
                  {d.filename} ({d.status})
                </option>
              ))}
            </select>
          </div>

          <div>
            <label className="text-xs font-semibold text-slate-700 block mb-1">
              Repair Action:
            </label>
            <select
              value={action}
              onChange={(e) => setAction(e.target.value as RepairActionRequest['action'])}
              className="w-full bg-slate-50 border border-slate-300 rounded-lg px-3 py-2 text-xs font-medium focus:ring-2 focus:ring-blue-500 focus:outline-none"
            >
              <option value="REPAIR_EMBEDDINGS">REPAIR_EMBEDDINGS (Re-embed chunks)</option>
              <option value="REGENERATE_CHUNKS">REGENERATE_CHUNKS (Re-chunk document)</option>
              <option value="RETRY_EXTRACTION">RETRY_EXTRACTION (Retry failed parsing)</option>
              <option value="RECONCILE_STALE">RECONCILE_STALE (Clear stalled state)</option>
              <option value="REINDEX_VERSION">REINDEX_VERSION (Stage version N+1)</option>
            </select>
          </div>

          <div className="flex flex-col justify-end gap-2">
            <div className="flex items-center gap-2">
              <input
                type="checkbox"
                id="dry-run-check"
                checked={dryRun}
                onChange={(e) => setDryRun(e.target.checked)}
                className="rounded border-slate-300 text-blue-600 focus:ring-blue-500"
              />
              <label htmlFor="dry-run-check" className="text-xs text-slate-600 font-medium">
                Dry Run (Preview changes only)
              </label>
            </div>

            <Button
              type="submit"
              disabled={isExecuting || !targetDocId}
              className="bg-blue-600 hover:bg-blue-700 text-xs font-medium h-9"
            >
              {isExecuting ? (
                <>
                  <Loader2 className="w-3.5 h-3.5 mr-1.5 animate-spin" />
                  Executing Repair...
                </>
              ) : dryRun ? (
                <>
                  <Eye className="w-3.5 h-3.5 mr-1.5" />
                  Preview Dry-Run
                </>
              ) : (
                <>
                  <Wrench className="w-3.5 h-3.5 mr-1.5" />
                  Execute Targeted Repair
                </>
              )}
            </Button>
          </div>
        </form>

        {/* Active Job Result Banner */}
        {activeJobResult && (
          <div
            className={`mt-4 p-4 rounded-xl border text-xs ${
              activeJobResult.status === 'COMPLETED'
                ? 'bg-emerald-50 border-emerald-200 text-emerald-900'
                : 'bg-rose-50 border-rose-200 text-rose-900'
            }`}
          >
            <div className="flex items-center justify-between font-bold">
              <span>Job {activeJobResult.job_id.slice(0, 8)}: {activeJobResult.action} ({activeJobResult.status})</span>
              {activeJobResult.dry_run && <Badge variant="outline">Dry Run</Badge>}
            </div>
            {activeJobResult.details && (
              <pre className="mt-2 bg-white/70 p-2 rounded text-[11px] overflow-auto">
                {JSON.stringify(activeJobResult.details, null, 2)}
              </pre>
            )}
          </div>
        )}
      </div>

      {/* Audit Log Table */}
      <div className="bg-white border border-slate-200 rounded-xl p-5 shadow-sm space-y-4">
        <div className="flex items-center justify-between">
          <h4 className="text-sm font-bold text-slate-900">
            Repair Execution Audit Log ({jobs.length} Records)
          </h4>
          <Button variant="outline" size="sm" onClick={fetchJobs} disabled={isLoading}>
            <RefreshCw className={`w-3.5 h-3.5 mr-1.5 ${isLoading ? 'animate-spin' : ''}`} />
            Refresh Audit Log
          </Button>
        </div>

        {jobs.length === 0 ? (
          <p className="text-xs text-slate-500 text-center py-6">
            No repair operations executed yet for this knowledge base.
          </p>
        ) : (
          <div className="space-y-2">
            {jobs.map((job) => (
              <div
                key={job.job_id}
                className="border border-slate-200 rounded-lg p-3 text-xs flex flex-col sm:flex-row sm:items-center justify-between gap-2"
              >
                <div className="flex items-center gap-2.5">
                  {job.status === 'COMPLETED' ? (
                    <CheckCircle2 className="w-4 h-4 text-emerald-500 shrink-0" />
                  ) : job.status === 'RUNNING' ? (
                    <Loader2 className="w-4 h-4 text-blue-500 animate-spin shrink-0" />
                  ) : (
                    <XCircle className="w-4 h-4 text-rose-500 shrink-0" />
                  )}
                  <div>
                    <div className="flex items-center gap-2">
                      <span className="font-semibold text-slate-900">{job.action}</span>
                      {job.dry_run && (
                        <Badge variant="outline" className="text-[10px] h-4">Dry Run</Badge>
                      )}
                      <Badge
                        variant={job.status === 'COMPLETED' ? 'default' : 'destructive'}
                        className="text-[10px] h-4"
                      >
                        {job.status}
                      </Badge>
                    </div>
                    {job.error_message && (
                      <p className="text-rose-600 text-[11px] mt-0.5">{job.error_message}</p>
                    )}
                  </div>
                </div>

                <div className="text-right text-[11px] text-slate-400">
                  {new Date(job.started_at).toLocaleString()}
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
