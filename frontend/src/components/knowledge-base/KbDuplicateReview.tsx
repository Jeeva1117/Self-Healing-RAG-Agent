import { useState, useEffect } from 'react';
import {
  Copy,
  FileText,
  AlertTriangle,
  HardDrive,
  RefreshCw,
  Search,
  Loader2,
  CheckCircle2,
} from 'lucide-react';

import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { useToast } from '@/context/ToastContext';
import { knowledgeBaseService } from '@/services/knowledgeBaseService';
import type { DuplicateReport, DuplicateCandidate } from '@/types/knowledgeBase';

interface Props {
  kbId: string;
}

function formatBytes(bytes: number): string {
  if (bytes === 0) return '0 B';
  const k = 1024;
  const sizes = ['B', 'KB', 'MB', 'GB'];
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  return `${parseFloat((bytes / Math.pow(k, i)).toFixed(1))} ${sizes[i]}`;
}

export function KbDuplicateReview({ kbId }: Props) {
  const { toast } = useToast();
  const [report, setReport] = useState<DuplicateReport | null>(null);
  const [threshold, setThreshold] = useState(0.85);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const fetchDuplicates = async (thresh = threshold) => {
    setIsLoading(true);
    setError(null);
    try {
      const data = await knowledgeBaseService.getDuplicates(kbId, thresh);
      setReport(data);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Failed to audit duplicates.';
      setError(msg);
      toast.error(msg, 'Duplicate Audit Error');
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    if (kbId) {
      fetchDuplicates(threshold);
    }
  }, [kbId]);

  if (isLoading) {
    return (
      <div className="bg-white border border-slate-200 rounded-xl p-16 text-center">
        <Loader2 className="w-8 h-8 text-blue-600 animate-spin mx-auto mb-3" />
        <p className="text-sm text-slate-600">Analyzing document hashes and text fingerprints...</p>
      </div>
    );
  }

  if (error) {
    return (
      <div className="bg-rose-50 border border-rose-200 rounded-xl p-6 text-center">
        <AlertTriangle className="w-8 h-8 text-rose-600 mx-auto mb-2" />
        <h4 className="font-semibold text-rose-900">Audit Failed</h4>
        <p className="text-sm text-rose-700 mt-1">{error}</p>
        <Button variant="outline" size="sm" onClick={() => fetchDuplicates(threshold)} className="mt-4 bg-white">
          <RefreshCw className="w-3.5 h-3.5 mr-1" /> Retry Audit
        </Button>
      </div>
    );
  }

  if (!report) return null;

  return (
    <div className="space-y-6">
      {/* Metric Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
        <div className="bg-white border border-slate-200 rounded-xl p-4 shadow-sm">
          <div className="flex items-center justify-between">
            <span className="text-xs font-medium text-slate-500">Exact Bit-for-Bit Duplicates</span>
            <Copy className="w-4 h-4 text-rose-500" />
          </div>
          <span className="text-2xl font-bold text-rose-600 mt-1 block">
            {report.exact_duplicates_count}
          </span>
          <span className="text-xs text-slate-400">matched via SHA-256</span>
        </div>

        <div className="bg-white border border-slate-200 rounded-xl p-4 shadow-sm">
          <div className="flex items-center justify-between">
            <span className="text-xs font-medium text-slate-500">Probable Near-Duplicates</span>
            <Search className="w-4 h-4 text-amber-500" />
          </div>
          <span className="text-2xl font-bold text-amber-600 mt-1 block">
            {report.near_duplicates_count}
          </span>
          <span className="text-xs text-slate-400">&ge; {threshold * 100}% text overlap</span>
        </div>

        <div className="bg-white border border-slate-200 rounded-xl p-4 shadow-sm">
          <div className="flex items-center justify-between">
            <span className="text-xs font-medium text-slate-500">Reclaimable Storage</span>
            <HardDrive className="w-4 h-4 text-blue-500" />
          </div>
          <span className="text-2xl font-bold text-blue-600 mt-1 block">
            {formatBytes(report.potential_storage_savings_bytes)}
          </span>
          <span className="text-xs text-slate-400">redundant duplicate bytes</span>
        </div>
      </div>

      {/* Threshold Controls */}
      <div className="bg-white border border-slate-200 rounded-xl p-4 shadow-sm flex flex-col sm:flex-row sm:items-center justify-between gap-3">
        <div className="flex items-center gap-4">
          <label className="text-xs font-semibold text-slate-700 uppercase tracking-wider">
            Near-Duplicate Sensitivity:
          </label>
          <div className="flex items-center gap-2">
            <input
              type="range"
              min="0.6"
              max="0.95"
              step="0.05"
              value={threshold}
              onChange={(e) => setThreshold(parseFloat(e.target.value))}
              className="w-32 h-2 bg-slate-200 rounded-lg appearance-none cursor-pointer accent-blue-600"
            />
            <span className="text-xs font-bold text-slate-700 w-10">
              {(threshold * 100).toFixed(0)}%
            </span>
          </div>
        </div>

        <Button
          variant="outline"
          size="sm"
          onClick={() => fetchDuplicates(threshold)}
          disabled={isLoading}
        >
          <RefreshCw className={`w-3.5 h-3.5 mr-1.5 ${isLoading ? 'animate-spin' : ''}`} />
          Run Detection
        </Button>
      </div>

      {/* Candidate List */}
      {report.candidates.length === 0 ? (
        <div className="bg-white border border-slate-200 rounded-xl p-12 text-center shadow-sm">
          <CheckCircle2 className="w-10 h-10 text-emerald-500 mx-auto mb-2" />
          <h4 className="text-base font-semibold text-slate-900">Zero Duplicates Detected</h4>
          <p className="text-sm text-slate-500 mt-1">
            All documents in this knowledge base contain distinct content fingerprints and unique text profiles.
          </p>
        </div>
      ) : (
        <div className="space-y-3">
          {report.candidates.map((c: DuplicateCandidate, idx) => (
            <div
              key={idx}
              className="bg-white border border-slate-200 rounded-xl p-4 shadow-sm space-y-3"
            >
              <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2">
                <div className="flex items-center gap-2">
                  <Badge
                    variant={c.match_type.startsWith('exact') ? 'destructive' : 'outline'}
                    className={
                      c.match_type.startsWith('exact')
                        ? ''
                        : 'border-amber-300 text-amber-800 bg-amber-50'
                    }
                  >
                    {c.match_type === 'exact_checksum'
                      ? 'Exact SHA-256 Checksum'
                      : c.match_type === 'exact_content'
                      ? 'Identical Text'
                      : 'Near Duplicate'}
                  </Badge>
                  <span className="text-xs font-semibold text-slate-600">
                    Similarity: {(c.similarity_score * 100).toFixed(1)}%
                  </span>
                  {c.storage_impact_bytes > 0 && (
                    <span className="text-xs text-slate-400">
                      • {formatBytes(c.storage_impact_bytes)}
                    </span>
                  )}
                </div>
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 text-xs">
                <div className="bg-slate-50 border border-slate-100 rounded-lg p-2.5">
                  <span className="text-slate-400 uppercase tracking-wider text-[10px] block font-semibold">
                    Primary / Authoritative Document:
                  </span>
                  <div className="flex items-center gap-1.5 mt-1 text-slate-900 font-medium">
                    <FileText className="w-3.5 h-3.5 text-blue-500 shrink-0" />
                    <span className="truncate">{c.primary_filename}</span>
                  </div>
                </div>

                <div className="bg-slate-50 border border-slate-100 rounded-lg p-2.5">
                  <span className="text-slate-400 uppercase tracking-wider text-[10px] block font-semibold">
                    Candidate Duplicate:
                  </span>
                  <div className="flex items-center gap-1.5 mt-1 text-slate-900 font-medium">
                    <Copy className="w-3.5 h-3.5 text-rose-500 shrink-0" />
                    <span className="truncate">{c.duplicate_filename}</span>
                  </div>
                </div>
              </div>

              <p className="text-xs text-slate-600 leading-relaxed bg-slate-50/70 p-2 rounded border border-slate-100">
                {c.explanation}
              </p>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
