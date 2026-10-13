import React, { useEffect, useState } from 'react';
import {
  Search,
  SlidersHorizontal,
  Sparkles,
  Layers,
  Database,
  Clock,
  ChevronDown,
  ChevronUp,
  AlertCircle,
  FileText,
  RefreshCw,
  GitCompare,
  Copy,
  Check,
} from 'lucide-react';
import { Card, CardContent } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Badge } from '@/components/ui/badge';
import { useNavigate } from 'react-router-dom';
import { knowledgeBaseService } from '@/services/knowledgeBaseService';
import { searchService } from '@/services/searchService';
import type { KnowledgeBase } from '@/types/knowledgeBase';
import type {
  ComparisonResponse,
  RetrievalLatencyBreakdown,
  RetrievalMode,
  RetrievalResultItem,
} from '@/types/search';

export function SearchPlaygroundPage() {
  const navigate = useNavigate();

  // Knowledge base selection
  const [knowledgeBases, setKnowledgeBases] = useState<KnowledgeBase[]>([]);
  const [selectedKbId, setSelectedKbId] = useState<string>('');
  const [loadingKbs, setLoadingKbs] = useState<boolean>(true);

  // Search parameters
  const [query, setQuery] = useState<string>('');
  const [mode, setMode] = useState<RetrievalMode>('hybrid');
  const [enableReranking, setEnableReranking] = useState<boolean>(true);
  const [candidateLimit, setCandidateLimit] = useState<number>(20);
  const [topK, setTopK] = useState<number>(5);
  const [similarityThreshold, setSimilarityThreshold] = useState<number>(0.0);
  const [showAdvanced, setShowAdvanced] = useState<boolean>(false);
  const [compareMode, setCompareMode] = useState<boolean>(false);

  // Results & execution state
  const [loading, setLoading] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);
  const [results, setResults] = useState<RetrievalResultItem[] | null>(null);
  const [latency, setLatency] = useState<RetrievalLatencyBreakdown | null>(null);
  const [comparisonData, setComparisonData] = useState<ComparisonResponse | null>(null);
  const [expandedChunks, setExpandedChunks] = useState<Set<string>>(new Set());
  const [copiedChunkId, setCopiedChunkId] = useState<string | null>(null);
  const [responseWarnings, setResponseWarnings] = useState<string[]>([]);
  const [rerankingApplied, setRerankingApplied] = useState<boolean | null>(null);

  // Load user's Knowledge Bases on mount
  useEffect(() => {
    async function fetchKbs() {
      setLoadingKbs(true);
      try {
        const resp = await knowledgeBaseService.listKnowledgeBases(0, 100);
        const items = resp.items || [];
        setKnowledgeBases(items);
        if (items.length > 0) {
          setSelectedKbId(items[0].id);
        }
      } catch (err: unknown) {
        console.error('Failed loading knowledge bases:', err);
      } finally {
        setLoadingKbs(false);
      }
    }
    fetchKbs();
  }, []);

  const toggleExpand = (chunkId: string) => {
    setExpandedChunks((prev) => {
      const next = new Set(prev);
      if (next.has(chunkId)) {
        next.delete(chunkId);
      } else {
        next.add(chunkId);
      }
      return next;
    });
  };

  const handleCopyText = async (chunkId: string, content: string) => {
    try {
      await navigator.clipboard.writeText(content);
      setCopiedChunkId(chunkId);
      setTimeout(() => setCopiedChunkId(null), 2000);
    } catch (err) {
      console.error('Failed to copy text:', err);
    }
  };

  const handleSearch = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!query.trim() || !selectedKbId) return;

    setLoading(true);
    setError(null);
    setResults(null);
    setComparisonData(null);
    setResponseWarnings([]);
    setRerankingApplied(null);

    try {
      if (compareMode) {
        const comp = await searchService.compare({
          knowledge_base_id: selectedKbId,
          query: query.trim(),
          candidate_limit: candidateLimit,
          top_k: topK,
          enable_reranking: enableReranking,
        });
        setComparisonData(comp);
        setLatency(comp.latency);
        if (comp.warnings && comp.warnings.length > 0) {
          setResponseWarnings(comp.warnings);
        }
      } else {
        const res = await searchService.search({
          knowledge_base_id: selectedKbId,
          query: query.trim(),
          mode,
          enable_reranking: enableReranking,
          candidate_limit: candidateLimit,
          top_k: topK,
          similarity_threshold: similarityThreshold,
        });
        setResults(res.results);
        setLatency(res.latency);
        setRerankingApplied(res.reranking_applied ?? null);
        if (res.warnings && res.warnings.length > 0) {
          setResponseWarnings(res.warnings);
        }
      }
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Retrieval request failed';
      setError(msg);
    } finally {
      setLoading(false);
    }
  };

  const getProvenanceBadge = (prov: string) => {
    switch (prov) {
      case 'hybrid':
        return (
          <Badge className="bg-indigo-100 text-indigo-800 border-indigo-200 hover:bg-indigo-100">
            <Layers className="w-3 h-3 mr-1" />
            Hybrid (Vector + BM25)
          </Badge>
        );
      case 'vector':
        return (
          <Badge className="bg-blue-100 text-blue-800 border-blue-200 hover:bg-blue-100">
            <Sparkles className="w-3 h-3 mr-1" />
            Vector Search
          </Badge>
        );
      case 'lexical':
        return (
          <Badge className="bg-emerald-100 text-emerald-800 border-emerald-200 hover:bg-emerald-100">
            <FileText className="w-3 h-3 mr-1" />
            BM25 Lexical
          </Badge>
        );
      default:
        return <Badge variant="outline">{prov}</Badge>;
    }
  };

  const renderResultCard = (item: RetrievalResultItem, index: number) => {
    const isExpanded = expandedChunks.has(item.chunk_id);
    const hasLongText = item.content.length > 280;
    const displayText = isExpanded || !hasLongText ? item.content : `${item.content.slice(0, 280)}...`;
    const isCopied = copiedChunkId === item.chunk_id;

    return (
      <Card
        key={`${item.chunk_id}-${index}`}
        className="border border-slate-200/90 shadow-sm hover:shadow-md transition-shadow duration-200 bg-white"
      >
        <CardContent className="p-5 space-y-3">
          {/* Top metadata & provenance bar */}
          <div className="flex flex-wrap items-center justify-between gap-2 border-b border-slate-100 pb-3">
            <div className="flex items-center gap-2">
              <span className="flex items-center justify-center w-7 h-7 rounded-full bg-blue-600 text-white font-bold text-xs shadow-sm">
                #{item.final_rank}
              </span>
              <span className="font-semibold text-slate-800 text-sm flex items-center gap-1.5">
                <FileText className="w-4 h-4 text-slate-400" />
                {item.document_name}
              </span>
              {item.page_number && (
                <Badge variant="outline" className="text-xs text-slate-600 bg-slate-50">
                  Page {item.page_number}
                </Badge>
              )}
              {item.section_title && (
                <Badge variant="outline" className="text-xs text-slate-600 bg-slate-50">
                  {item.section_title}
                </Badge>
              )}
            </div>
            <div className="flex items-center gap-2">
              {getProvenanceBadge(item.stage_provenance)}
              <button
                type="button"
                onClick={() => handleCopyText(item.chunk_id, item.content)}
                className="inline-flex items-center gap-1 text-xs text-slate-500 hover:text-slate-800 bg-slate-100 hover:bg-slate-200 px-2 py-1 rounded transition-colors"
                title="Copy chunk content"
              >
                {isCopied ? (
                  <>
                    <Check className="w-3.5 h-3.5 text-emerald-600" />
                    <span className="text-emerald-700 font-medium">Copied!</span>
                  </>
                ) : (
                  <>
                    <Copy className="w-3.5 h-3.5 text-slate-500" />
                    <span>Copy</span>
                  </>
                )}
              </button>
            </div>
          </div>

          {/* Scores audit trail with transparent multi-stage scores */}
          <div className="flex flex-wrap items-center gap-2 py-1 bg-slate-50/70 px-3 rounded-lg border border-slate-100 text-xs">
            <span className="font-medium text-slate-500">Scores:</span>
            {(item.vector_score !== null && item.vector_score !== undefined) && (
              <span className="inline-flex items-center gap-1 font-mono text-blue-700 bg-blue-50 px-2 py-0.5 rounded border border-blue-100" title="Semantic Cosine Similarity">
                <strong>Vector:</strong> {item.vector_score.toFixed(4)}
                {item.vector_rank && <span className="text-blue-500 text-[10px]">(r:{item.vector_rank})</span>}
              </span>
            )}
            {(item.lexical_score !== null && item.lexical_score !== undefined) && (
              <span className="inline-flex items-center gap-1 font-mono text-emerald-700 bg-emerald-50 px-2 py-0.5 rounded border border-emerald-100" title="BM25 Lexical Score">
                <strong>BM25:</strong> {item.lexical_score.toFixed(4)}
                {item.lexical_rank && <span className="text-emerald-500 text-[10px]">(r:{item.lexical_rank})</span>}
              </span>
            )}
            {(item.rrf_score !== null && item.rrf_score !== undefined) && (
              <span className="inline-flex items-center gap-1 font-mono text-indigo-700 bg-indigo-50 px-2 py-0.5 rounded border border-indigo-100" title="Reciprocal Rank Fusion Score">
                <strong>RRF:</strong> {item.rrf_score.toFixed(6)}
              </span>
            )}
            {(item.reranker_score !== null && item.reranker_score !== undefined) && (
              <span className="inline-flex items-center gap-1 font-mono font-semibold text-amber-900 bg-amber-100/80 px-2 py-0.5 rounded border border-amber-200" title="Cross-Encoder Neural Rerank Score">
                <strong>Reranker:</strong> {item.reranker_score.toFixed(6)}
              </span>
            )}
          </div>

          {/* Chunk Text Content */}
          <div className="text-sm text-slate-700 leading-relaxed font-sans whitespace-pre-wrap bg-slate-50/40 p-3 rounded-lg border border-slate-100/80">
            {displayText}
          </div>

          {/* Bottom Footer & Expand toggle with provenance metadata */}
          <div className="flex flex-wrap items-center justify-between text-xs text-slate-400 pt-1 gap-2">
            <div className="flex flex-wrap items-center gap-2 font-mono">
              <span>
                Chunk #{item.chunk_index} • {item.character_count} chars • {item.token_count || '~'} tokens
              </span>
              <span className="text-slate-300">|</span>
              <span title={`Document ID: ${item.document_id}`}>
                Doc: {item.document_id.slice(0, 8)}...
              </span>
              {item.document_version_id && (
                <Badge variant="outline" className="text-[10px] text-slate-500 py-0 px-1 bg-slate-50">
                  ver: {item.document_version_id.slice(0, 8)}
                </Badge>
              )}
            </div>
            {hasLongText && (
              <button
                type="button"
                onClick={() => toggleExpand(item.chunk_id)}
                className="text-blue-600 hover:text-blue-800 font-medium inline-flex items-center gap-1 transition-colors"
              >
                {isExpanded ? (
                  <>
                    Show less <ChevronUp className="w-3.5 h-3.5" />
                  </>
                ) : (
                  <>
                    Show full chunk <ChevronDown className="w-3.5 h-3.5" />
                  </>
                )}
              </button>
            )}
          </div>
        </CardContent>
      </Card>
    );
  };

  return (
    <div className="space-y-6 max-w-7xl mx-auto pb-12">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <div className="flex items-center gap-2.5">
            <h1 className="text-2xl font-bold text-slate-900 tracking-tight">Retrieval Playground</h1>
            <Badge className="bg-blue-600 text-white font-medium hover:bg-blue-600">
              Hybrid RRF + Reranker
            </Badge>
          </div>
          <p className="text-sm text-slate-500 mt-1">
            Evaluate real-time Hybrid Retrieval (Vector + BM25Okapi + Reciprocal Rank Fusion + Neural Cross-Encoder Reranking).
          </p>
        </div>
        <Button
          variant="outline"
          size="sm"
          onClick={() => navigate('/knowledge-base')}
          className="border-slate-300 text-slate-700 hover:bg-slate-50"
        >
          <Database className="w-4 h-4 mr-1.5 text-blue-600" />
          Manage Documents
        </Button>
      </div>

      {/* Main Search Controls Card */}
      <Card className="border border-slate-200/90 shadow-sm bg-white">
        <CardContent className="p-6 space-y-5">
          <form onSubmit={handleSearch} className="space-y-5">
            {/* Knowledge Base selector & Mode switcher */}
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div>
                <label className="block text-xs font-semibold text-slate-600 uppercase tracking-wider mb-2">
                  Knowledge Base
                </label>
                {loadingKbs ? (
                  <div className="h-10 bg-slate-100 rounded-lg animate-pulse" />
                ) : knowledgeBases.length === 0 ? (
                  <div className="p-3 bg-amber-50 text-amber-800 text-xs rounded-lg border border-amber-200 flex items-center justify-between">
                    <span>No Knowledge Bases found. Create one first!</span>
                    <Button size="sm" variant="outline" onClick={() => navigate('/knowledge-base')}>
                      Create KB
                    </Button>
                  </div>
                ) : (
                  <select
                    value={selectedKbId}
                    onChange={(e) => setSelectedKbId(e.target.value)}
                    disabled={loading}
                    className="w-full h-11 px-3.5 text-sm bg-white border border-slate-300 rounded-xl focus:ring-2 focus:ring-blue-500 focus:border-blue-500 outline-none transition-all font-medium text-slate-800"
                  >
                    {knowledgeBases.map((kb) => (
                      <option key={kb.id} value={kb.id}>
                        {kb.name} ({kb.document_count ?? 0} docs)
                      </option>
                    ))}
                  </select>
                )}
              </div>

              {/* Mode Selection Tabs */}
              <div>
                <label className="block text-xs font-semibold text-slate-600 uppercase tracking-wider mb-2">
                  Retrieval Strategy
                </label>
                <div className="grid grid-cols-3 gap-1.5 p-1 bg-slate-100 rounded-xl border border-slate-200/80">
                  <button
                    type="button"
                    disabled={loading || compareMode}
                    onClick={() => setMode('hybrid')}
                    className={`h-9 text-xs font-semibold rounded-lg transition-all flex items-center justify-center gap-1.5 ${
                      mode === 'hybrid' && !compareMode
                        ? 'bg-white text-indigo-700 shadow-sm border border-slate-200/60'
                        : 'text-slate-600 hover:text-slate-900'
                    }`}
                  >
                    <Layers className="w-3.5 h-3.5" />
                    Hybrid (RRF)
                  </button>
                  <button
                    type="button"
                    disabled={loading || compareMode}
                    onClick={() => setMode('vector')}
                    className={`h-9 text-xs font-semibold rounded-lg transition-all flex items-center justify-center gap-1.5 ${
                      mode === 'vector' && !compareMode
                        ? 'bg-white text-blue-700 shadow-sm border border-slate-200/60'
                        : 'text-slate-600 hover:text-slate-900'
                    }`}
                  >
                    <Sparkles className="w-3.5 h-3.5" />
                    Vector Only
                  </button>
                  <button
                    type="button"
                    disabled={loading || compareMode}
                    onClick={() => setMode('lexical')}
                    className={`h-9 text-xs font-semibold rounded-lg transition-all flex items-center justify-center gap-1.5 ${
                      mode === 'lexical' && !compareMode
                        ? 'bg-white text-emerald-700 shadow-sm border border-slate-200/60'
                        : 'text-slate-600 hover:text-slate-900'
                    }`}
                  >
                    <FileText className="w-3.5 h-3.5" />
                    BM25 Lexical
                  </button>
                </div>
              </div>
            </div>

            {/* Query Input Box */}
            <div className="relative">
              <Search className="absolute left-4 top-1/2 -translate-y-1/2 w-5 h-5 text-slate-400" />
              <Input
                type="text"
                placeholder="Enter query to evaluate retrieval (e.g. 'Python machine learning experience', 'refund policy')..."
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                disabled={loading}
                className="pl-12 pr-32 h-12 text-base rounded-xl border-slate-300 focus:border-blue-500 focus:ring-blue-500"
              />
              <Button
                type="submit"
                disabled={loading || !query.trim() || !selectedKbId}
                className="absolute right-2 top-1/2 -translate-y-1/2 h-9 px-5 rounded-lg bg-blue-600 hover:bg-blue-700 text-white font-medium shadow-sm transition-all"
              >
                {loading ? (
                  <>
                    <RefreshCw className="w-4 h-4 mr-2 animate-spin" />
                    Retrieving...
                  </>
                ) : (
                  <>Search</>
                )}
              </Button>
            </div>

            {/* Secondary Controls Bar: Reranker switch & compare toggle */}
            <div className="flex flex-wrap items-center justify-between gap-4 pt-2 border-t border-slate-100">
              <div className="flex flex-wrap items-center gap-6">
                {/* Cross-encoder reranker toggle */}
                <label className="flex items-center gap-2 cursor-pointer text-xs font-semibold text-slate-700 select-none">
                  <input
                    type="checkbox"
                    checked={enableReranking}
                    onChange={(e) => setEnableReranking(e.target.checked)}
                    disabled={loading}
                    className="w-4 h-4 text-blue-600 rounded border-slate-300 focus:ring-blue-500 accent-blue-600 cursor-pointer"
                  />
                  <span>Cross-Encoder Reranker</span>
                  <Badge variant="outline" className="text-[10px] bg-amber-50 text-amber-800 border-amber-300">
                    FlashRank ONNX
                  </Badge>
                </label>

                {/* Compare modes toggle */}
                <label className="flex items-center gap-2 cursor-pointer text-xs font-semibold text-slate-700 select-none">
                  <input
                    type="checkbox"
                    checked={compareMode}
                    onChange={(e) => setCompareMode(e.target.checked)}
                    disabled={loading}
                    className="w-4 h-4 text-indigo-600 rounded border-slate-300 focus:ring-indigo-500 accent-indigo-600 cursor-pointer"
                  />
                  <GitCompare className="w-3.5 h-3.5 text-indigo-600" />
                  <span>Side-by-Side Comparison View</span>
                </label>
              </div>

              {/* Advanced Parameters Toggle */}
              <button
                type="button"
                onClick={() => setShowAdvanced(!showAdvanced)}
                className="text-xs font-medium text-slate-500 hover:text-slate-800 flex items-center gap-1 transition-colors"
              >
                <SlidersHorizontal className="w-3.5 h-3.5" />
                {showAdvanced ? 'Hide Advanced Settings' : 'Advanced Settings'}
              </button>
            </div>

            {/* Advanced Parameter Sliders */}
            {showAdvanced && (
              <div className="p-4 bg-slate-50 rounded-xl border border-slate-200/80 grid grid-cols-1 md:grid-cols-3 gap-5 animate-in fade-in duration-200">
                <div>
                  <div className="flex justify-between items-center text-xs font-semibold text-slate-700 mb-1.5">
                    <span>Candidates per Retriever:</span>
                    <span className="text-blue-600 font-mono">{candidateLimit}</span>
                  </div>
                  <input
                    type="range"
                    min="5"
                    max="50"
                    step="5"
                    value={candidateLimit}
                    onChange={(e) => setCandidateLimit(parseInt(e.target.value, 10))}
                    disabled={loading}
                    className="w-full accent-blue-600 cursor-pointer"
                  />
                </div>

                <div>
                  <div className="flex justify-between items-center text-xs font-semibold text-slate-700 mb-1.5">
                    <span>Final Top-K Results:</span>
                    <span className="text-blue-600 font-mono">{topK}</span>
                  </div>
                  <input
                    type="range"
                    min="1"
                    max="20"
                    step="1"
                    value={topK}
                    onChange={(e) => setTopK(parseInt(e.target.value, 10))}
                    disabled={loading}
                    className="w-full accent-blue-600 cursor-pointer"
                  />
                </div>

                <div>
                  <div className="flex justify-between items-center text-xs font-semibold text-slate-700 mb-1.5">
                    <span>Similarity Threshold:</span>
                    <span className="text-blue-600 font-mono">{similarityThreshold.toFixed(2)}</span>
                  </div>
                  <input
                    type="range"
                    min="0"
                    max="0.9"
                    step="0.05"
                    value={similarityThreshold}
                    onChange={(e) => setSimilarityThreshold(parseFloat(e.target.value))}
                    disabled={loading}
                    className="w-full accent-blue-600 cursor-pointer"
                  />
                </div>
              </div>
            )}
          </form>
        </CardContent>
      </Card>

      {/* Latency Breakdown Bar */}
      {latency && (
        <div className="bg-gradient-to-r from-slate-900 to-slate-800 text-white p-4 rounded-xl shadow-sm border border-slate-700 flex flex-wrap items-center justify-between gap-4">
          <div className="flex items-center gap-2 text-sm font-semibold text-slate-200">
            <Clock className="w-4 h-4 text-blue-400" />
            <span>Execution Latency Breakdown:</span>
          </div>
          <div className="flex flex-wrap items-center gap-4 text-xs font-mono">
            <div className="bg-slate-800/80 px-2.5 py-1 rounded border border-slate-700">
              <span className="text-slate-400">Vector: </span>
              <span className="text-blue-300 font-bold">{latency.vector_ms}ms</span>
            </div>
            <div className="bg-slate-800/80 px-2.5 py-1 rounded border border-slate-700">
              <span className="text-slate-400">BM25: </span>
              <span className="text-emerald-300 font-bold">{latency.lexical_ms}ms</span>
            </div>
            <div className="bg-slate-800/80 px-2.5 py-1 rounded border border-slate-700">
              <span className="text-slate-400">RRF Fusion: </span>
              <span className="text-indigo-300 font-bold">{latency.fusion_ms}ms</span>
            </div>
            <div className="bg-slate-800/80 px-2.5 py-1 rounded border border-slate-700">
              <span className="text-slate-400">Rerank: </span>
              <span className="text-amber-300 font-bold">{latency.rerank_ms}ms</span>
            </div>
            <div className="bg-blue-600/30 px-3 py-1 rounded border border-blue-500/50">
              <span className="text-slate-300">Total: </span>
              <span className="text-white font-bold">{latency.total_ms}ms</span>
            </div>
          </div>
        </div>
      )}

      {/* Engine Warnings Banner */}
      {responseWarnings.length > 0 && (
        <div className="p-4 bg-amber-50 text-amber-900 border border-amber-200 rounded-xl flex items-start gap-3">
          <AlertCircle className="w-5 h-5 text-amber-600 shrink-0 mt-0.5" />
          <div className="flex-1 text-sm">
            <p className="font-semibold">Retrieval Diagnostics</p>
            {responseWarnings.map((w, idx) => (
              <p key={idx} className="mt-0.5 text-amber-800">{w}</p>
            ))}
          </div>
        </div>
      )}

      {/* Error Banner */}
      {error && (
        <div className="p-4 bg-red-50 text-red-900 border border-red-200 rounded-xl flex items-start gap-3">
          <AlertCircle className="w-5 h-5 text-red-600 shrink-0 mt-0.5" />
          <div className="flex-1 text-sm">
            <p className="font-semibold">Retrieval Error</p>
            <p className="mt-0.5 text-red-800/90">{error}</p>
          </div>
        </div>
      )}

      {/* Loading Skeleton */}
      {loading && (
        <div className="space-y-4">
          <div className="p-8 text-center bg-white rounded-xl border border-slate-200">
            <RefreshCw className="w-8 h-8 text-blue-600 animate-spin mx-auto mb-3" />
            <p className="text-base font-semibold text-slate-800">Executing Retrieval Engine</p>
            <p className="text-xs text-slate-500 mt-1">
              Computing dense query embeddings, generating BM25 scores, and running neural cross-encoder...
            </p>
          </div>
          {[1, 2, 3].map((i) => (
            <div key={i} className="h-32 bg-slate-100 rounded-xl animate-pulse" />
          ))}
        </div>
      )}

      {/* Comparison View (Side-by-side) */}
      {comparisonData && !loading && (
        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <h2 className="text-lg font-bold text-slate-900 flex items-center gap-2">
              <GitCompare className="w-5 h-5 text-indigo-600" />
              Side-by-Side Retrieval Comparison
            </h2>
          </div>

          <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
            {/* Column 1: Vector Results */}
            <div className="space-y-3">
              <div className="p-3 bg-blue-50 border border-blue-200 rounded-xl flex items-center justify-between">
                <span className="text-sm font-bold text-blue-950 flex items-center gap-1.5">
                  <Sparkles className="w-4 h-4 text-blue-600" />
                  Semantic Vector
                </span>
                <Badge variant="outline" className="bg-white text-blue-800">
                  {comparisonData.vector_results.length} results
                </Badge>
              </div>
              <div className="space-y-3">
                {comparisonData.vector_results.length === 0 ? (
                  <p className="text-xs text-slate-400 p-4 text-center">No vector matches</p>
                ) : (
                  comparisonData.vector_results.map((r, i) => renderResultCard(r, i))
                )}
              </div>
            </div>

            {/* Column 2: Lexical (BM25) Results */}
            <div className="space-y-3">
              <div className="p-3 bg-emerald-50 border border-emerald-200 rounded-xl flex items-center justify-between">
                <span className="text-sm font-bold text-emerald-950 flex items-center gap-1.5">
                  <FileText className="w-4 h-4 text-emerald-600" />
                  BM25 Lexical
                </span>
                <Badge variant="outline" className="bg-white text-emerald-800">
                  {comparisonData.lexical_results.length} results
                </Badge>
              </div>
              <div className="space-y-3">
                {comparisonData.lexical_results.length === 0 ? (
                  <p className="text-xs text-slate-400 p-4 text-center">No keyword matches</p>
                ) : (
                  comparisonData.lexical_results.map((r, i) => renderResultCard(r, i))
                )}
              </div>
            </div>

            {/* Column 3: Hybrid (Fused + Reranked) Results */}
            <div className="space-y-3">
              <div className="p-3 bg-indigo-50 border border-indigo-200 rounded-xl flex items-center justify-between">
                <span className="text-sm font-bold text-indigo-950 flex items-center gap-1.5">
                  <Layers className="w-4 h-4 text-indigo-600" />
                  Hybrid + Reranked
                </span>
                <Badge variant="outline" className="bg-white text-indigo-800">
                  {comparisonData.hybrid_results.length} results
                </Badge>
              </div>
              <div className="space-y-3">
                {comparisonData.hybrid_results.length === 0 ? (
                  <p className="text-xs text-slate-400 p-4 text-center">No hybrid matches</p>
                ) : (
                  comparisonData.hybrid_results.map((r, i) => renderResultCard(r, i))
                )}
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Standard Results List View */}
      {results && !loading && !comparisonData && (
        <div className="space-y-4">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <div className="flex items-center gap-3">
              <h2 className="text-lg font-bold text-slate-900">
                Retrieved Results ({results.length})
              </h2>
              {rerankingApplied === true && (
                <Badge className="bg-emerald-100 text-emerald-800 border-emerald-300 text-xs">
                  Neural Rerank: Applied
                </Badge>
              )}
              {rerankingApplied === false && enableReranking && (
                <Badge className="bg-amber-100 text-amber-800 border-amber-300 text-xs">
                  Rerank: Fallback to RRF
                </Badge>
              )}
              {!enableReranking && (
                <Badge variant="outline" className="text-slate-500 text-xs">
                  Rerank: Disabled
                </Badge>
              )}
            </div>
            <span className="text-xs text-slate-500">
              Ranked by {enableReranking && rerankingApplied ? 'Cross-Encoder Relevance' : mode === 'hybrid' ? 'Reciprocal Rank Fusion' : mode}
            </span>
          </div>

          {results.length === 0 ? (
            <div className="rounded-xl border border-dashed border-slate-300 p-12 text-center bg-slate-50/50">
              <Search className="w-8 h-8 text-slate-400 mx-auto mb-2" />
              <p className="text-sm font-semibold text-slate-700">No matching chunks found</p>
              <p className="text-xs text-slate-500 mt-1 max-w-md mx-auto">
                Try modifying your search terms, reducing the similarity threshold, or switching to Hybrid mode.
              </p>
            </div>
          ) : (
            <div className="space-y-4">
              {results.map((item, idx) => renderResultCard(item, idx))}
            </div>
          )}
        </div>
      )}

      {/* Initial Clean State */}
      {!results && !comparisonData && !loading && !error && (
        <div className="rounded-xl border border-dashed border-slate-300 p-12 text-center bg-slate-50/50">
          <Layers className="w-10 h-10 text-slate-400 mx-auto mb-3" />
          <h3 className="text-base font-semibold text-slate-700">Ready to Search</h3>
          <p className="text-xs text-slate-500 mt-1 max-w-md mx-auto">
            Select a Knowledge Base and enter a query above to see real-time vector similarities, BM25 scores, and neural rerankings.
          </p>
        </div>
      )}
    </div>
  );
}
