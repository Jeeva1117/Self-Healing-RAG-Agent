import React, { useState } from 'react';
import {
  GitBranch,
  RefreshCw,
  ShieldCheck,
  Loader2,
} from 'lucide-react';

import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { useToast } from '@/context/ToastContext';
import { knowledgeBaseService } from '@/services/knowledgeBaseService';
import type { DocumentItem, DocumentVersionHistoryResponse } from '@/types/knowledgeBase';

interface Props {
  kbId: string;
  documents: DocumentItem[];
  onRefreshDocs?: () => void;
}

export function KbVersioningView({ kbId, documents, onRefreshDocs }: Props) {
  const { toast } = useToast();
  const [selectedDocId, setSelectedDocId] = useState<string>(documents[0]?.id || '');
  const [history, setHistory] = useState<DocumentVersionHistoryResponse | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [isReindexing, setIsReindexing] = useState(false);

  const fetchVersions = async (docId: string) => {
    if (!docId) return;
    setIsLoading(true);
    try {
      const data = await knowledgeBaseService.getDocumentVersions(kbId, docId);
      setHistory(data);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Failed to fetch version history.';
      toast.error(msg, 'Version History Error');
    } finally {
      setIsLoading(false);
    }
  };

  React.useEffect(() => {
    if (selectedDocId) {
      fetchVersions(selectedDocId);
    }
  }, [selectedDocId]);

  const handleReindex = async () => {
    if (!selectedDocId) return;
    setIsReindexing(true);
    try {
      const result = await knowledgeBaseService.reindexDocument(kbId, selectedDocId);
      toast.success(
        `Successfully staged and promoted Version ${result.version_number} (${result.chunk_count} chunks).`,
        'Re-indexing Complete'
      );
      await fetchVersions(selectedDocId);
      if (onRefreshDocs) onRefreshDocs();
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Re-indexing failed.';
      toast.error(msg, 'Re-indexing Error');
    } finally {
      setIsReindexing(false);
    }
  };

  if (documents.length === 0) {
    return (
      <div className="bg-white border border-slate-200 rounded-xl p-12 text-center shadow-sm">
        <GitBranch className="w-10 h-10 text-slate-400 mx-auto mb-2" />
        <h4 className="text-base font-semibold text-slate-900">No Documents Available</h4>
        <p className="text-sm text-slate-500 mt-1">Upload a document to inspect and manage its version lineage.</p>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Notice Banner */}
      <div className="bg-blue-50 border border-blue-200 rounded-xl p-4 flex items-start gap-3 text-xs text-blue-800">
        <ShieldCheck className="w-5 h-5 text-blue-600 shrink-0 mt-0.5" />
        <div>
          <span className="font-bold text-blue-900 block">Zero-Downtime Safe Re-indexing Guarantee</span>
          <span>
            When re-indexing, the system stages Version N+1 with inactive chunks. Embeddings and parsing are validated
            in full before atomically promoting the new version. The prior active version remains retrieval-ready until promotion completes.
          </span>
        </div>
      </div>

      {/* Document Selector & Action */}
      <div className="bg-white border border-slate-200 rounded-xl p-4 shadow-sm flex flex-col sm:flex-row sm:items-center justify-between gap-3">
        <div className="flex items-center gap-3">
          <label className="text-xs font-semibold text-slate-500 uppercase tracking-wider">
            Select Document:
          </label>
          <select
            value={selectedDocId}
            onChange={(e) => setSelectedDocId(e.target.value)}
            className="bg-slate-50 border border-slate-300 text-slate-900 text-sm font-semibold rounded-lg px-3 py-1.5 focus:ring-2 focus:ring-blue-500 focus:outline-none max-w-xs"
          >
            {documents.map((d) => (
              <option key={d.id} value={d.id}>
                {d.filename} (v{d.active_version || 1})
              </option>
            ))}
          </select>
        </div>

        <Button
          variant="default"
          size="sm"
          onClick={handleReindex}
          disabled={isReindexing || isLoading}
          className="bg-blue-600 hover:bg-blue-700 font-medium"
        >
          <RefreshCw className={`w-3.5 h-3.5 mr-1.5 ${isReindexing ? 'animate-spin' : ''}`} />
          {isReindexing ? 'Staging Version...' : 'Re-index Document'}
        </Button>
      </div>

      {/* Version History Table / List */}
      {isLoading ? (
        <div className="bg-white border border-slate-200 rounded-xl p-12 text-center">
          <Loader2 className="w-6 h-6 text-blue-600 animate-spin mx-auto mb-2" />
          <p className="text-xs text-slate-600">Loading version records...</p>
        </div>
      ) : history ? (
        <div className="bg-white border border-slate-200 rounded-xl p-4 shadow-sm space-y-4">
          <div className="flex items-center justify-between">
            <h4 className="text-sm font-bold text-slate-900">
              Version History for &quot;{history.filename}&quot; ({history.total_versions} Revisions)
            </h4>
            <Badge variant="outline" className="text-blue-700 border-blue-200 bg-blue-50">
              Active: v{history.active_version_number}
            </Badge>
          </div>

          <div className="space-y-3">
            {history.versions.map((ver) => (
              <div
                key={ver.id}
                className={`border rounded-lg p-3.5 flex flex-col sm:flex-row sm:items-center justify-between gap-3 text-xs ${
                  ver.is_active ? 'border-blue-300 bg-blue-50/20' : 'border-slate-200 bg-slate-50/50'
                }`}
              >
                <div className="flex items-center gap-3">
                  <div
                    className={`w-7 h-7 rounded-full flex items-center justify-center font-bold text-xs ${
                      ver.is_active ? 'bg-blue-600 text-white' : 'bg-slate-200 text-slate-600'
                    }`}
                  >
                    v{ver.version_number}
                  </div>
                  <div>
                    <div className="flex items-center gap-2">
                      <span className="font-semibold text-slate-900">
                        Revision #{ver.version_number}
                      </span>
                      {ver.is_active && (
                        <Badge variant="default" className="bg-emerald-600 text-[10px] h-4 px-1.5">
                          Active Index
                        </Badge>
                      )}
                    </div>
                    <div className="text-slate-500 text-[11px] mt-0.5 flex items-center gap-2">
                      <span>Checksum: <code className="bg-slate-100 px-1 py-0.5 rounded">{ver.checksum.slice(0, 12)}...</code></span>
                      <span>•</span>
                      <span>{ver.chunk_count} chunks indexed</span>
                    </div>
                  </div>
                </div>

                <div className="text-right text-[11px] text-slate-400">
                  {new Date(ver.created_at).toLocaleString()}
                </div>
              </div>
            ))}
          </div>
        </div>
      ) : null}
    </div>
  );
}
