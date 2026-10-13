import { useState, useEffect } from 'react';
import {
  AlertTriangle,
  Lightbulb,
  FileQuestion,
  Search,
  Scale,
  Loader2,
} from 'lucide-react';
import { Badge } from '@/components/ui/badge';
import { useToast } from '@/context/ToastContext';
import { knowledgeBaseService } from '@/services/knowledgeBaseService';

import type { CoverageReport, ConflictReport } from '@/types/knowledgeBase';

interface Props {
  kbId: string;
}

export function KbCoverageInsights({ kbId }: Props) {
  const { toast } = useToast();
  const [coverage, setCoverage] = useState<CoverageReport | null>(null);
  const [conflicts, setConflicts] = useState<ConflictReport | null>(null);
  const [isLoading, setIsLoading] = useState(false);

  const fetchData = async () => {
    setIsLoading(true);
    try {
      const [covData, confData] = await Promise.all([
        knowledgeBaseService.getCoverage(kbId),
        knowledgeBaseService.getConflicts(kbId),
      ]);
      setCoverage(covData);
      setConflicts(confData);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Failed to analyze knowledge coverage.';
      toast.error(msg, 'Coverage Analysis Error');
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    if (kbId) {
      fetchData();
    }
  }, [kbId]);

  if (isLoading) {
    return (
      <div className="bg-white border border-slate-200 rounded-xl p-16 text-center">
        <Loader2 className="w-8 h-8 text-blue-600 animate-spin mx-auto mb-3" />
        <p className="text-sm text-slate-600">Analyzing retrieval traces, evidence gaps, and contradictions...</p>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Overview Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
        <div className="bg-white border border-slate-200 rounded-xl p-4 shadow-sm">
          <div className="flex items-center justify-between">
            <span className="text-xs font-medium text-slate-500">Traces Analyzed</span>
            <Search className="w-4 h-4 text-blue-500" />
          </div>
          <span className="text-2xl font-bold text-slate-900 mt-1 block">
            {coverage?.total_queries_analyzed || 0}
          </span>
          <span className="text-xs text-slate-400">empirical user queries</span>
        </div>

        <div className="bg-white border border-slate-200 rounded-xl p-4 shadow-sm">
          <div className="flex items-center justify-between">
            <span className="text-xs font-medium text-slate-500">Insufficient Evidence Rate</span>
            <AlertTriangle className="w-4 h-4 text-amber-500" />
          </div>
          <span className="text-2xl font-bold text-amber-600 mt-1 block">
            {coverage ? `${(coverage.insufficient_evidence_rate * 100).toFixed(1)}%` : '0.0%'}
          </span>
          <span className="text-xs text-slate-400">queries lacking evidence</span>
        </div>

        <div className="bg-white border border-slate-200 rounded-xl p-4 shadow-sm">
          <div className="flex items-center justify-between">
            <span className="text-xs font-medium text-slate-500">Detected Conflicts</span>
            <Scale className="w-4 h-4 text-rose-500" />
          </div>
          <span className="text-2xl font-bold text-rose-600 mt-1 block">
            {conflicts?.total_conflicts_detected || 0}
          </span>
          <span className="text-xs text-slate-400">contradictory policy pairs</span>
        </div>
      </div>

      {/* Recommendations */}
      {coverage && coverage.recommendations.length > 0 && (
        <div className="bg-white border border-slate-200 rounded-xl p-4 shadow-sm space-y-3">
          <div className="flex items-center gap-2 text-sm font-bold text-slate-900">
            <Lightbulb className="w-4 h-4 text-amber-500" />
            Empirical Coverage Recommendations
          </div>
          <div className="space-y-2">
            {coverage.recommendations.map((rec, idx) => (
              <div key={idx} className="bg-amber-50/60 border border-amber-200 rounded-lg p-2.5 text-xs text-amber-900">
                {rec}
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Evidence Gaps */}
      <div className="bg-white border border-slate-200 rounded-xl p-4 shadow-sm space-y-3">
        <h4 className="text-sm font-bold text-slate-900 flex items-center gap-2">
          <FileQuestion className="w-4 h-4 text-blue-500" />
          Queries with Insufficient Evidence ({coverage?.evidence_gaps.length || 0})
        </h4>

        {coverage?.evidence_gaps.length === 0 ? (
          <p className="text-xs text-slate-500">No evidence sufficiency gaps recorded in current query history.</p>
        ) : (
          <div className="space-y-2">
            {coverage?.evidence_gaps.map((gap, idx) => (
              <div key={idx} className="border border-slate-200 rounded-lg p-3 text-xs space-y-1">
                <div className="flex items-center justify-between">
                  <span className="font-semibold text-slate-900">&quot;{gap.query}&quot;</span>
                  <Badge variant="outline" className="text-[10px]">
                    Failed {gap.frequency}x
                  </Badge>
                </div>
                <p className="text-slate-500 text-[11px]">{gap.suggested_action}</p>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Contradictions & Conflicts */}
      {conflicts && conflicts.items.length > 0 && (
        <div className="bg-white border border-slate-200 rounded-xl p-4 shadow-sm space-y-3">
          <h4 className="text-sm font-bold text-slate-900 flex items-center gap-2 text-rose-800">
            <Scale className="w-4 h-4 text-rose-600" />
            Detected Policy Contradictions ({conflicts.items.length})
          </h4>
          <div className="space-y-3">
            {conflicts.items.map((item, idx) => (
              <div key={idx} className="bg-rose-50/30 border border-rose-200 rounded-lg p-3 text-xs space-y-2">
                <div className="flex items-center justify-between font-semibold text-rose-900">
                  <span>{item.topic}</span>
                  <Badge variant="destructive" className="text-[10px]">Contradiction</Badge>
                </div>
                <p className="text-slate-700">{item.conflict_summary}</p>
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-2 text-[11px]">
                  <div className="bg-white p-2 rounded border border-slate-200">
                    <span className="font-semibold text-slate-800 block">{item.document_a_name} (v{item.document_a_version}):</span>
                    <span className="text-slate-600 italic">&quot;{item.document_a_excerpt}&quot;</span>
                  </div>
                  <div className="bg-white p-2 rounded border border-slate-200">
                    <span className="font-semibold text-slate-800 block">{item.document_b_name} (v{item.document_b_version}):</span>
                    <span className="text-slate-600 italic">&quot;{item.document_b_excerpt}&quot;</span>
                  </div>
                </div>
                <p className="text-slate-500 text-[11px]">Guidance: {item.remediation_guidance}</p>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
