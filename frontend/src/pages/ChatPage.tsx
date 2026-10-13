import React, { useState, useRef, useEffect, useMemo } from 'react';
import {
  Send,
  Paperclip,
  Copy,
  RotateCcw,
  ThumbsUp,
  ThumbsDown,
  Layers,
  SlidersHorizontal,
  ShieldCheck,
  Sparkles,
  ExternalLink,
  CheckCircle2,
  Clock,
  FileText,
  PanelRightClose,
  PanelRightOpen,
  Database,
  AlertCircle,
  ChevronDown,
  ChevronUp,
} from 'lucide-react';
import { useNavigate } from 'react-router-dom';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Drawer } from '@/components/ui/drawer';
import { MarkdownView } from '@/components/ui/markdown-view';
import { CitationCard, type CitationItem } from '@/components/ui/citation-card';
import { ConfidenceIndicator } from '@/components/ui/confidence-indicator';
import { useToast } from '@/context/ToastContext';
import { cn } from '@/lib/utils';
import { chatService } from '@/services/chatService';
import { knowledgeBaseService } from '@/services/knowledgeBaseService';
import type { KnowledgeBase } from '@/types/knowledgeBase';
import type { ChatMessage } from '@/types/chat';

// Self-Healing pipeline states
type SelfHealingState =
  | 'Not Triggered'
  | 'Recovery Triggered'
  | 'Query Rewriting'
  | 'Re-Retrieval'
  | 'Reranking'
  | 'Regeneration'
  | 'Verification'
  | 'Recovered';

const SELF_HEALING_STEPS: SelfHealingState[] = [
  'Not Triggered',
  'Recovery Triggered',
  'Query Rewriting',
  'Re-Retrieval',
  'Reranking',
  'Regeneration',
  'Verification',
  'Recovered',
];

export function ChatPage() {
  const { toast } = useToast();
  const navigate = useNavigate();
  const messagesEndRef = useRef<HTMLDivElement>(null);

  // Knowledge base selection state
  const [knowledgeBases, setKnowledgeBases] = useState<KnowledgeBase[]>([]);
  const [selectedKbId, setSelectedKbId] = useState<string>('');
  const [loadingKbs, setLoadingKbs] = useState<boolean>(true);

  // Chat input and generation state
  const [inputPrompt, setInputPrompt] = useState('');
  const [isGenerating, setIsGenerating] = useState(false);
  const [selectedCitation, setSelectedCitation] = useState<CitationItem | null>(null);
  const [rightPanelTab, setRightPanelTab] = useState<'workflow' | 'sources' | 'metadata'>('workflow');
  const [isRightPanelOpen, setIsRightPanelOpen] = useState(true);
  const [selfHealingState, setSelfHealingState] = useState<SelfHealingState>('Not Triggered');
  const [collapsedSources, setCollapsedSources] = useState<Record<string, boolean>>({});

  const toggleSources = (msgId: string) => {
    setCollapsedSources((prev) => ({ ...prev, [msgId]: !prev[msgId] }));
  };

  // Messages state with honest initial onboarding message
  const [messages, setMessages] = useState<ChatMessage[]>([
    {
      id: 'm-welcome',
      role: 'assistant',
      content:
        '👋 Welcome to the grounded RAG assistant!\n\nSelect a **Knowledge Base** from the top bar to begin asking questions. Every answer is retrieved using real-time Hybrid Retrieval (Dense Vector + BM25Okapi + Reciprocal Rank Fusion + Neural Cross-Encoder Reranking) directly from your uploaded document chunks, with exact sentence-level source citations.',
      timestamp: 'Just now',
      citations: [],
      confidence: null,
      verificationStatus: 'grounded_evidence',
    },
  ]);

  // Load user's Knowledge Bases on mount
  useEffect(() => {
    async function fetchKnowledgeBases() {
      setLoadingKbs(true);
      try {
        const resp = await knowledgeBaseService.listKnowledgeBases(0, 100);
        const items = resp.items || [];
        setKnowledgeBases(items);
        if (items.length > 0) {
          // If Python KB exists, prefer it as default for instant testing
          const pythonKb = items.find((kb) => kb.name.toLowerCase().includes('python'));
          setSelectedKbId(pythonKb ? pythonKb.id : items[0].id);
        }
      } catch (err: unknown) {
        console.error('Failed loading knowledge bases:', err);
        toast.error('Could not load knowledge bases.');
      } finally {
        setLoadingKbs(false);
      }
    }
    fetchKnowledgeBases();
  }, [toast]);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, isGenerating]);

  // Find the active or latest assistant message for right panel display
  const latestAssistantMessage = useMemo(() => {
    for (let i = messages.length - 1; i >= 0; i--) {
      if (messages[i].role === 'assistant' && messages[i].id !== 'm-welcome') {
        return messages[i];
      }
    }
    return null;
  }, [messages]);

  const activeCitations = useMemo(() => {
    return latestAssistantMessage?.citations || [];
  }, [latestAssistantMessage]);

  const selectedKb = useMemo(() => {
    return knowledgeBases.find((kb) => kb.id === selectedKbId);
  }, [knowledgeBases, selectedKbId]);

  // Dynamic suggested questions based on selected Knowledge Base
  const suggestedQuestions = useMemo(() => {
    if (!selectedKb) return ['What are the key topics in this document?'];
    const nameLower = selectedKb.name.toLowerCase();
    if (nameLower.includes('python')) {
      return [
        'What are operators in Python?',
        'How do functions work in Python?',
        'Explain lists and strings in Python',
      ];
    }
    if (nameLower.includes('resume')) {
      return [
        'What are the primary technical skills listed?',
        'Summarize the candidate work experience',
        'What education and degrees are mentioned?',
      ];
    }
    return [
      `What are the main topics in ${selectedKb.name}?`,
      'Summarize key facts and findings',
      'List important definitions and rules',
    ];
  }, [selectedKb]);

  const handleSendMessage = async (textToSend?: string) => {
    const query = (textToSend || inputPrompt).trim();
    if (!query || isGenerating) return;

    if (!selectedKbId) {
      toast.error('Please select a Knowledge Base before asking questions.');
      return;
    }

    const userMessage: ChatMessage = {
      id: `m-${Date.now()}`,
      role: 'user',
      content: query,
      timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
    };

    setMessages((prev) => [...prev, userMessage]);
    setInputPrompt('');
    setIsGenerating(true);

    try {
      const resp = await chatService.sendMessage({
        knowledge_base_id: selectedKbId,
        prompt: query,
        top_k: 5,
      });

      const assistantMessage: ChatMessage = {
        id: resp.id,
        role: 'assistant',
        content: resp.content,
        timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
        citations: resp.citations,
        confidence: resp.confidence,
        verificationStatus: resp.verification_status,
        isInsufficientEvidence: resp.is_insufficient_evidence,
        answerType: resp.answer_type || resp.answerType,
        retrievalLatency: resp.retrieval_latency || undefined,
        generationMs: resp.generation_ms,
        totalMs: resp.total_ms,
        model: resp.model,
        tokensUsed: resp.tokens_used,
        retryCount: resp.retry_count ?? 0,
        workflowSteps: resp.workflow_steps ?? [],
      };

      setMessages((prev) => [...prev, assistantMessage]);

      if (resp.retry_count && resp.retry_count > 0) {
        setSelfHealingState('Re-Retrieval');
      } else if (resp.is_insufficient_evidence) {
        setSelfHealingState('Not Triggered');
      } else {
        setSelfHealingState('Recovered');
      }
    } catch (err: unknown) {
      const errMsg = err instanceof Error ? err.message : 'Chat request failed';
      toast.error(errMsg);
      const errorMsg: ChatMessage = {
        id: `m-${Date.now() + 1}`,
        role: 'assistant',
        content: `⚠️ **LLM Request Error:** ${errMsg}`,
        timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
        isInsufficientEvidence: false,
        answerType: 'provider_error',
      };
      setMessages((prev) => [...prev, errorMsg]);
    } finally {
      setIsGenerating(false);
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === 'Enter') {
      e.preventDefault();
      handleSendMessage();
    }
  };

  const handleCitationClick = (citationId: number) => {
    const found = activeCitations.find((c) => c.id === citationId);
    if (found) {
      setSelectedCitation(found);
    }
  };

  const handleCopyMessage = (text: string) => {
    navigator.clipboard.writeText(text);
    toast.success('Answer copied to clipboard');
  };

  const handleRegenerate = () => {
    for (let i = messages.length - 1; i >= 0; i--) {
      if (messages[i].role === 'user') {
        handleSendMessage(messages[i].content);
        return;
      }
    }
    toast.info('No previous question found to regenerate.');
  };

  return (
    <div className="flex flex-col xl:flex-row gap-6 min-h-[calc(100vh-6.5rem)] pb-6">
      {/* ========================================================
          LEFT / CENTER: MAIN CHAT WORKSPACE
      ======================================================== */}
      <div className="flex-1 flex flex-col min-w-0 space-y-6">
        {/* Main Header & KB Scope Selector */}
        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
          <div>
            <h1 className="text-2xl sm:text-3xl font-bold tracking-tight text-slate-900 dark:text-white flex items-center gap-2">
              <span>Good morning, Jeeva!</span>
              <span className="text-2xl">👋</span>
            </h1>
            <p className="text-xs sm:text-sm text-slate-500 dark:text-slate-400 mt-1">
              Ask questions, get accurate answers grounded in your uploaded documents with verifiable citations.
            </p>
          </div>

          <div className="flex flex-wrap items-center gap-2">
            {/* Dedicated Knowledge Base Selector */}
            <div className="flex items-center gap-2 bg-slate-50 dark:bg-slate-800/80 px-3 py-1.5 rounded-xl border border-slate-200 dark:border-slate-700">
              <Database className="h-4 w-4 text-blue-600 dark:text-blue-400 shrink-0" />
              <label htmlFor="chat-kb-select" className="text-xs font-semibold text-slate-600 dark:text-slate-300">
                KB:
              </label>
              {loadingKbs ? (
                <span className="text-xs text-slate-400">Loading...</span>
              ) : knowledgeBases.length === 0 ? (
                <span className="text-xs text-amber-600">No KBs found</span>
              ) : (
                <select
                  id="chat-kb-select"
                  value={selectedKbId}
                  onChange={(e) => setSelectedKbId(e.target.value)}
                  disabled={isGenerating}
                  className="bg-transparent text-xs font-medium text-slate-800 dark:text-slate-100 focus:outline-none cursor-pointer max-w-[180px] sm:max-w-[220px] truncate"
                >
                  {knowledgeBases.map((kb) => (
                    <option
                      key={kb.id}
                      value={kb.id}
                      className="dark:bg-slate-900 text-slate-900 dark:text-slate-100"
                    >
                      {kb.name} ({kb.document_count ?? 0} docs)
                    </option>
                  ))}
                </select>
              )}
            </div>

            <Button
              variant="outline"
              size="sm"
              onClick={() => setIsRightPanelOpen(!isRightPanelOpen)}
              className="gap-1.5 text-xs text-slate-600 border-slate-200 bg-white hover:bg-slate-50 dark:bg-slate-900 dark:border-slate-800 dark:text-slate-300"
            >
              {isRightPanelOpen ? (
                <>
                  <PanelRightClose className="h-4 w-4 text-slate-500" />
                  <span className="hidden sm:inline">Hide Agent Panel</span>
                </>
              ) : (
                <>
                  <PanelRightOpen className="h-4 w-4 text-blue-600" />
                  <span className="hidden sm:inline">Show Agent Panel</span>
                </>
              )}
            </Button>
          </div>
        </div>

        {/* Warning banner if user has no KBs */}
        {!loadingKbs && knowledgeBases.length === 0 && (
          <div className="p-4 rounded-xl border border-amber-200 bg-amber-50/70 text-amber-900 text-xs flex items-center justify-between dark:bg-amber-950/30 dark:border-amber-900 dark:text-amber-300">
            <div className="flex items-center gap-2">
              <AlertCircle className="h-4 w-4 text-amber-600" />
              <span>No Knowledge Bases found. Please create one and upload documents to enable grounded retrieval.</span>
            </div>
            <Button size="sm" variant="outline" onClick={() => navigate('/knowledge-base')}>
              Create Knowledge Base
            </Button>
          </div>
        )}

        {/* Four Feature Cards */}
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-3 sm:gap-4">
          {/* Card 1: Hybrid Search */}
          <div
            onClick={() => handleSendMessage(suggestedQuestions[0] || 'Explain the main concepts')}
            className="flex items-center gap-3 p-3.5 rounded-xl border border-slate-200 bg-white shadow-2xs hover:border-blue-300 hover:shadow-xs hover:bg-blue-50/20 transition-all cursor-pointer dark:bg-slate-900 dark:border-slate-800 dark:hover:border-blue-600"
          >
            <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-blue-50 text-blue-600 dark:bg-blue-900/30 dark:text-blue-400">
              <Layers className="h-5 w-5" />
            </div>
            <div className="truncate">
              <div className="font-semibold text-xs text-slate-900 dark:text-slate-100 truncate">
                Hybrid Search
              </div>
              <div className="text-[11px] text-slate-500 dark:text-slate-400 truncate">
                BM25 + Dense Vector
              </div>
            </div>
          </div>

          {/* Card 2: Reranking */}
          <div
            onClick={() => handleSendMessage(suggestedQuestions[1] || 'Explain in detail with code examples')}
            className="flex items-center gap-3 p-3.5 rounded-xl border border-slate-200 bg-white shadow-2xs hover:border-blue-300 hover:shadow-xs hover:bg-blue-50/20 transition-all cursor-pointer dark:bg-slate-900 dark:border-slate-800 dark:hover:border-blue-600"
          >
            <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-blue-50 text-blue-600 dark:bg-blue-900/30 dark:text-blue-400">
              <SlidersHorizontal className="h-5 w-5" />
            </div>
            <div className="truncate">
              <div className="font-semibold text-xs text-slate-900 dark:text-slate-100 truncate">
                Neural Reranking
              </div>
              <div className="text-[11px] text-slate-500 dark:text-slate-400 truncate">
                FlashRank Cross-Encoder
              </div>
            </div>
          </div>

          {/* Card 3: Verification */}
          <div
            onClick={() => handleSendMessage(suggestedQuestions[2] || 'Provide citations from document')}
            className="flex items-center gap-3 p-3.5 rounded-xl border border-slate-200 bg-white shadow-2xs hover:border-blue-300 hover:shadow-xs hover:bg-blue-50/20 transition-all cursor-pointer dark:bg-slate-900 dark:border-slate-800 dark:hover:border-blue-600"
          >
            <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-blue-50 text-blue-600 dark:bg-blue-900/30 dark:text-blue-400">
              <ShieldCheck className="h-5 w-5" />
            </div>
            <div className="truncate">
              <div className="font-semibold text-xs text-slate-900 dark:text-slate-100 truncate">
                Citation Grounding
              </div>
              <div className="text-[11px] text-slate-500 dark:text-slate-400 truncate">
                Exact Chunk Evidence
              </div>
            </div>
          </div>

          {/* Card 4: Self-Healing */}
          <div
            onClick={() => setRightPanelTab('workflow')}
            className="flex items-center gap-3 p-3.5 rounded-xl border border-slate-200 bg-white shadow-2xs hover:border-blue-300 hover:shadow-xs hover:bg-blue-50/20 transition-all cursor-pointer dark:bg-slate-900 dark:border-slate-800 dark:hover:border-blue-600"
          >
            <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-blue-50 text-blue-600 dark:bg-blue-900/30 dark:text-blue-400">
              <Sparkles className="h-5 w-5" />
            </div>
            <div className="truncate">
              <div className="font-semibold text-xs text-slate-900 dark:text-slate-100 truncate">
                Pipeline Telemetry
              </div>
              <div className="text-[11px] text-slate-500 dark:text-slate-400 truncate">
                Live Retrieval Traces
              </div>
            </div>
          </div>
        </div>

        {/* SELF-HEALING UI CARD */}
        <div className="rounded-2xl border border-blue-200 bg-blue-50/50 p-4 sm:p-5 shadow-2xs transition-all dark:bg-blue-950/20 dark:border-blue-900/50">
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 pb-3 border-b border-blue-100 dark:border-blue-900/40">
            <div className="flex items-center gap-2.5">
              <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-blue-600 text-white shadow-xs">
                <RotateCcw className="h-4 w-4" />
              </div>
              <div>
                <div className="flex items-center gap-2">
                  <span className="font-bold text-sm text-slate-900 dark:text-slate-100">
                    Self-Healing Engine
                  </span>
                  <Badge variant="outline" size="sm" className="bg-white text-blue-700 border-blue-300 text-[10px] font-semibold dark:bg-blue-900/40 dark:text-blue-300">
                    Core USP
                  </Badge>
                </div>
                <div className="text-[11px] text-slate-500 dark:text-slate-400">
                  Automated query rewriting, fallback vector expansion, and hallucination self-correction
                </div>
              </div>
            </div>

            <div className="flex items-center gap-2">
              <span className="text-[11px] font-medium text-slate-600 dark:text-slate-300">Current State:</span>
              <Badge
                variant="outline"
                className={cn(
                  'font-semibold text-xs px-2.5 py-0.5',
                  selfHealingState === 'Recovered'
                    ? 'bg-emerald-50 text-emerald-700 border-emerald-300 dark:bg-emerald-950/50 dark:text-emerald-300'
                    : selfHealingState === 'Not Triggered'
                    ? 'bg-slate-100 text-slate-600 border-slate-200 dark:bg-slate-800 dark:text-slate-400'
                    : 'bg-blue-600 text-white border-blue-600 animate-pulse'
                )}
              >
                {selfHealingState}
              </Badge>
            </div>
          </div>

          {/* Recovery Cycle Pipeline Pills */}
          <div className="pt-3">
            <div className="text-[11px] font-semibold text-slate-500 uppercase tracking-wider mb-2">
              Recovery Cycle Pipeline
            </div>
            <div className="grid grid-cols-2 sm:grid-cols-4 lg:grid-cols-8 gap-1.5">
              {SELF_HEALING_STEPS.map((step, idx) => {
                const isSelected = step === selfHealingState;
                const isCompleted = step === 'Recovered' && selfHealingState === 'Recovered';

                return (
                  <button
                    key={step}
                    onClick={() => {
                      setSelfHealingState(step);
                    }}
                    className={cn(
                      'flex flex-col items-center justify-center p-2 rounded-lg border text-center transition-all cursor-pointer text-[10px]',
                      isSelected
                        ? isCompleted
                          ? 'border-emerald-500 bg-emerald-600 text-white font-semibold shadow-xs'
                          : 'border-blue-600 bg-blue-600 text-white font-semibold shadow-xs'
                        : 'border-slate-200 bg-white text-slate-600 hover:border-blue-300 hover:bg-blue-50/30 dark:bg-slate-900 dark:border-slate-800 dark:text-slate-400'
                    )}
                  >
                    <span className="opacity-75 font-mono text-[9px]">0{idx + 1}</span>
                    <span className="truncate w-full font-medium">{step}</span>
                  </button>
                );
              })}
            </div>
          </div>
        </div>

        {/* AI ANSWER & CONVERSATION STREAM AREA */}
        <div className="space-y-4">
          {messages.map((msg) => (
            <React.Fragment key={msg.id}>
              {msg.role === 'user' ? (
                /* User Prompt Bubble */
                <div className="flex justify-end">
                  <div className="max-w-xl rounded-2xl bg-blue-600 text-white px-4 py-3 text-xs sm:text-sm font-medium shadow-sm">
                    {msg.content}
                  </div>
                </div>
              ) : (
                /* AI Answer Card */
                <div className="rounded-2xl border border-slate-200 bg-white p-5 sm:p-6 shadow-sm space-y-4 dark:bg-slate-900 dark:border-slate-800">
                  {/* Top Bar: Honest Verification Status & Confidence */}
                  <div className="flex flex-wrap items-center justify-between gap-3 pb-3 border-b border-slate-100 dark:border-slate-800">
                    <div className="flex flex-wrap items-center gap-2">
                      {/* Provider & Model Badge */}
                      <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-md text-[11px] font-medium bg-blue-50 text-blue-700 border border-blue-200 dark:bg-blue-950/50 dark:text-blue-300 dark:border-blue-800/60">
                        <Sparkles className="h-3 w-3 text-blue-600 dark:text-blue-400" />
                        <span>Groq · {msg.model || 'llama-3.3-70b-versatile'}</span>
                      </span>

                      {/* Answer Classification Badge */}
                      {msg.answerType === 'general_ai' || msg.verificationStatus === 'general_ai_answer' ? (
                        <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-md text-[11px] font-medium bg-purple-50 text-purple-700 border border-purple-200 dark:bg-purple-950/50 dark:text-purple-300 dark:border-purple-800/60">
                          <Sparkles className="h-3 w-3 text-purple-600 dark:text-purple-400" />
                          <span>General AI answer</span>
                        </span>
                      ) : msg.isInsufficientEvidence || msg.answerType === 'insufficient_evidence' ? (
                        <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-md text-[11px] font-medium bg-amber-50 text-amber-700 border border-amber-200 dark:bg-amber-950/50 dark:text-amber-300 dark:border-amber-800/60">
                          <AlertCircle className="h-3 w-3 text-amber-600 dark:text-amber-400" />
                          <span>Insufficient document evidence</span>
                        </span>
                      ) : msg.answerType === 'provider_error' ? (
                        <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-md text-[11px] font-medium bg-rose-50 text-rose-700 border border-rose-200 dark:bg-rose-950/50 dark:text-rose-300 dark:border-rose-800/60">
                          <AlertCircle className="h-3 w-3 text-rose-600 dark:text-rose-400" />
                          <span>LLM provider unavailable</span>
                        </span>
                      ) : (
                        <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-md text-[11px] font-medium bg-emerald-50 text-emerald-700 border border-emerald-200 dark:bg-emerald-950/50 dark:text-emerald-300 dark:border-emerald-800/60">
                          <CheckCircle2 className="h-3 w-3 text-emerald-600 dark:text-emerald-400" />
                          <span>Document-grounded answer</span>
                        </span>
                      )}

                      {/* Citation count if grounded */}
                      {msg.citations && msg.citations.length > 0 && (
                        <span className="text-[11px] text-slate-500 dark:text-slate-400 hidden sm:inline">
                          • {msg.citations.length} cited sources
                        </span>
                      )}
                    </div>

                    <ConfidenceIndicator score={msg.confidence} />
                  </div>

                  {/* Answer Text with Markdown & Citations */}
                  <div className="text-[15px] sm:text-base text-gray-800 dark:text-slate-200 leading-[1.6]">
                    <MarkdownView
                      content={msg.content}
                      onCitationClick={handleCitationClick}
                    />
                  </div>

                  {/* Collapsible Sources Cards */}
                  {msg.citations && msg.citations.length > 0 && (
                    <div className="pt-3 border-t border-slate-100 dark:border-slate-800 space-y-2.5">
                      <button
                        type="button"
                        onClick={() => toggleSources(msg.id)}
                        className="w-full flex items-center justify-between text-left py-1 hover:text-blue-600 transition-colors cursor-pointer group"
                      >
                        <span className="text-xs font-semibold text-gray-900 dark:text-slate-100 flex items-center gap-1.5">
                          <FileText className="h-4 w-4 text-blue-600" />
                          <span>Sources & Evidence ({msg.citations.length})</span>
                        </span>
                        <div className="flex items-center gap-1 text-[11px] text-slate-400 group-hover:text-blue-600">
                          <span>{collapsedSources[msg.id] ? 'Show sources' : 'Hide sources'}</span>
                          {collapsedSources[msg.id] ? (
                            <ChevronDown className="h-3.5 w-3.5" />
                          ) : (
                            <ChevronUp className="h-3.5 w-3.5" />
                          )}
                        </div>
                      </button>

                      {!collapsedSources[msg.id] && (
                        <div className="grid gap-2.5 sm:grid-cols-2 pt-1">
                          {msg.citations.map((c) => (
                            <CitationCard
                              key={`${c.id}-${c.documentId || c.title}`}
                              citation={c}
                              onOpenSnippet={(item) => setSelectedCitation(item)}
                            />
                          ))}
                        </div>
                      )}
                    </div>
                  )}

                  {/* Action Toolbar */}
                  <div className="flex items-center justify-between pt-3 border-t border-slate-100 dark:border-slate-800 text-slate-500">
                    <div className="flex items-center gap-1.5">
                      <button
                        onClick={() => handleCopyMessage(msg.content)}
                        className="inline-flex items-center gap-1 px-2.5 py-1 rounded-md text-xs font-medium text-slate-600 hover:text-slate-900 hover:bg-slate-100 dark:text-slate-400 dark:hover:text-slate-100 transition-colors cursor-pointer"
                        title="Copy answer"
                      >
                        <Copy className="h-3.5 w-3.5" />
                        <span>Copy</span>
                      </button>

                      <button
                        onClick={handleRegenerate}
                        disabled={isGenerating}
                        className="inline-flex items-center gap-1 px-2.5 py-1 rounded-md text-xs font-medium text-slate-600 hover:text-slate-900 hover:bg-slate-100 dark:text-slate-400 dark:hover:text-slate-100 transition-colors cursor-pointer disabled:opacity-50"
                        title="Regenerate"
                      >
                        <RotateCcw className="h-3.5 w-3.5" />
                        <span>Regenerate</span>
                      </button>
                    </div>

                    <div className="flex items-center gap-1">
                      <button
                        onClick={() => toast.success('Helpful feedback recorded')}
                        className="p-1.5 rounded-md text-slate-500 hover:text-blue-600 hover:bg-blue-50 dark:hover:bg-slate-800 transition-colors cursor-pointer"
                        title="Helpful"
                      >
                        <ThumbsUp className="h-3.5 w-3.5" />
                      </button>
                      <button
                        onClick={() => toast.info('Feedback tagged for dataset review')}
                        className="p-1.5 rounded-md text-slate-500 hover:text-rose-600 hover:bg-rose-50 dark:hover:bg-slate-800 transition-colors cursor-pointer"
                        title="Unhelpful"
                      >
                        <ThumbsDown className="h-3.5 w-3.5" />
                      </button>
                    </div>
                  </div>
                </div>
              )}
            </React.Fragment>
          ))}

          {isGenerating && (
            <div className="flex items-center gap-3 p-4 rounded-xl border border-blue-200 bg-blue-50/70 text-blue-900 text-xs sm:text-sm font-medium dark:bg-slate-900 dark:border-slate-800 dark:text-blue-300 shadow-sm animate-pulse">
              <Sparkles className="h-4 w-4 animate-spin text-blue-600 dark:text-blue-400 shrink-0" />
              <span>Generating response with Groq (llama-3.3-70b-versatile)...</span>
            </div>
          )}

          <div ref={messagesEndRef} />
        </div>

        {/* CHAT INPUT & SUGGESTED PILLS */}
        <div className="space-y-3 pt-2">
          {/* Input Box */}
          <div className="rounded-2xl border border-slate-200 bg-white p-2 sm:p-2.5 shadow-sm transition-all focus-within:border-blue-500 focus-within:ring-2 focus-within:ring-blue-100 dark:bg-slate-900 dark:border-slate-800 dark:focus-within:ring-blue-900/30">
            <div className="flex items-center gap-2">
              <button
                type="button"
                onClick={() => navigate('/knowledge-base')}
                className="p-2 rounded-xl text-slate-400 hover:text-blue-600 hover:bg-slate-100 transition-colors cursor-pointer dark:hover:bg-slate-800"
                title="Manage uploaded documents"
              >
                <Paperclip className="h-4 w-4" />
              </button>

              <input
                type="text"
                value={inputPrompt}
                onChange={(e) => setInputPrompt(e.target.value)}
                onKeyDown={handleKeyDown}
                placeholder={selectedKb ? `Ask about "${selectedKb.name}"...` : 'Select a Knowledge Base and ask a question...'}
                disabled={isGenerating || knowledgeBases.length === 0}
                className="flex-1 bg-transparent px-2 py-1.5 text-xs sm:text-sm text-slate-900 placeholder:text-slate-400 focus:outline-none dark:text-slate-100 disabled:opacity-50"
              />

              <Button
                size="sm"
                onClick={() => handleSendMessage()}
                disabled={!inputPrompt.trim() || isGenerating || knowledgeBases.length === 0}
                className="rounded-xl bg-blue-600 hover:bg-blue-700 text-white font-medium px-4 gap-1.5 shadow-sm shadow-blue-500/20 disabled:opacity-50"
              >
                <span>Send</span>
                <Send className="h-3.5 w-3.5" />
              </Button>
            </div>
          </div>

          {/* Suggested Question Pills */}
          <div className="flex items-center gap-2 overflow-x-auto pb-1">
            <span className="text-[11px] font-semibold text-slate-400 shrink-0">Try asking:</span>
            {suggestedQuestions.map((q) => (
              <button
                key={q}
                onClick={() => handleSendMessage(q)}
                disabled={isGenerating}
                className="shrink-0 px-3 py-1.5 rounded-full border border-blue-200 bg-blue-50/70 text-blue-700 text-xs font-medium hover:bg-blue-100 hover:border-blue-300 transition-all cursor-pointer dark:bg-blue-950/40 dark:border-blue-900 dark:text-blue-300 disabled:opacity-50"
              >
                {q}
              </button>
            ))}
          </div>
        </div>
      </div>

      {/* ========================================================
          RIGHT WORKFLOW PANEL
      ======================================================== */}
      {isRightPanelOpen && (
        <aside className="w-full xl:w-96 rounded-2xl border border-slate-200 bg-white p-4 sm:p-5 shadow-sm space-y-4 shrink-0 transition-all dark:bg-slate-900 dark:border-slate-800">
          {/* Panel Header & Tabs */}
          <div className="flex items-center justify-between pb-3 border-b border-slate-100 dark:border-slate-800">
            <div className="flex rounded-lg bg-slate-100 p-1 dark:bg-slate-800">
              <button
                onClick={() => setRightPanelTab('workflow')}
                className={cn(
                  'px-3 py-1.5 rounded-md text-xs font-semibold transition-all cursor-pointer',
                  rightPanelTab === 'workflow'
                    ? 'bg-white text-blue-600 shadow-2xs dark:bg-slate-900 dark:text-blue-400'
                    : 'text-slate-500 hover:text-slate-800 dark:text-slate-400'
                )}
              >
                Agent Workflow
              </button>
              <button
                onClick={() => setRightPanelTab('sources')}
                className={cn(
                  'px-3 py-1.5 rounded-md text-xs font-semibold transition-all cursor-pointer',
                  rightPanelTab === 'sources'
                    ? 'bg-white text-blue-600 shadow-2xs dark:bg-slate-900 dark:text-blue-400'
                    : 'text-slate-500 hover:text-slate-800 dark:text-slate-400'
                )}
              >
                Sources
              </button>
              <button
                onClick={() => setRightPanelTab('metadata')}
                className={cn(
                  'px-3 py-1.5 rounded-md text-xs font-semibold transition-all cursor-pointer',
                  rightPanelTab === 'metadata'
                    ? 'bg-white text-blue-600 shadow-2xs dark:bg-slate-900 dark:text-blue-400'
                    : 'text-slate-500 hover:text-slate-800 dark:text-slate-400'
                )}
              >
                Metadata
              </button>
            </div>

            <button
              onClick={() => setIsRightPanelOpen(false)}
              className="xl:hidden p-1 rounded-md text-slate-400 hover:bg-slate-100"
            >
              ✕
            </button>
          </div>

          {/* TAB 1: AGENT WORKFLOW TIMELINE */}
          {rightPanelTab === 'workflow' && (
            <div className="space-y-4">
              <div className="flex items-center justify-between">
                <span className="text-xs font-bold text-slate-900 dark:text-slate-100">
                  Execution Pipeline
                </span>
                <Badge
                  variant="outline"
                  size="sm"
                  className={cn(
                    'font-mono text-[10px]',
                    latestAssistantMessage
                      ? 'bg-emerald-50 text-emerald-700 border-emerald-200'
                      : 'bg-slate-50 text-slate-500 border-slate-200'
                  )}
                >
                  {latestAssistantMessage ? 'Status: Completed' : 'Status: Ready'}
                </Badge>
              </div>

              {/* Vertical Step Timeline with Real Measured Latency */}
              <div className="relative pl-6 space-y-4 before:absolute before:left-2.5 before:top-2 before:bottom-2 before:w-0.5 before:bg-slate-200 dark:before:bg-slate-800">
                {latestAssistantMessage?.workflowSteps && latestAssistantMessage.workflowSteps.length > 0 ? (
                  latestAssistantMessage.workflowSteps.map((step, idx) => (
                    <div key={`${step.step_id}-${idx}`} className="relative group">
                      <div
                        className={cn(
                          'absolute -left-6 top-0.5 flex h-5 w-5 items-center justify-center rounded-full text-white shadow-2xs ring-4 ring-white dark:ring-slate-900',
                          step.status === 'completed'
                            ? 'bg-blue-600'
                            : step.status === 'failed'
                            ? 'bg-rose-500'
                            : 'bg-amber-500'
                        )}
                      >
                        {step.status === 'completed' ? (
                          <CheckCircle2 className="h-3 w-3" />
                        ) : (
                          <AlertCircle className="h-3 w-3" />
                        )}
                      </div>
                      <div>
                        <div className="flex items-center justify-between">
                          <span className="font-semibold text-xs text-slate-900 dark:text-slate-100">
                            {idx + 1}. {step.name}
                          </span>
                          <span className="text-[10px] font-mono text-slate-400">
                            {Math.round(step.duration_ms)}ms
                          </span>
                        </div>
                        {step.description && (
                          <p className="text-[11px] text-slate-500 mt-0.5 leading-relaxed">
                            {step.description}
                          </p>
                        )}
                      </div>
                    </div>
                  ))
                ) : (
                  <>
                    {/* Default Standby Timeline */}
                    <div className="relative group">
                      <div className="absolute -left-6 top-0.5 flex h-5 w-5 items-center justify-center rounded-full bg-slate-300 text-slate-700 shadow-2xs ring-4 ring-white dark:bg-slate-700 dark:text-slate-300 dark:ring-slate-900">
                        <CheckCircle2 className="h-3 w-3" />
                      </div>
                      <div>
                        <div className="flex items-center justify-between">
                          <span className="font-semibold text-xs text-slate-900 dark:text-slate-100">
                            1. Query Analysis & Scope Validation
                          </span>
                          <span className="text-[10px] font-mono text-slate-400">Standby</span>
                        </div>
                        <p className="text-[11px] text-slate-500 mt-0.5">
                          LangGraph query normalization, intent detection, and tenant scope checks
                        </p>
                      </div>
                    </div>

                    <div className="relative group">
                      <div className="absolute -left-6 top-0.5 flex h-5 w-5 items-center justify-center rounded-full bg-slate-300 text-slate-700 shadow-2xs ring-4 ring-white dark:bg-slate-700 dark:text-slate-300 dark:ring-slate-900">
                        <CheckCircle2 className="h-3 w-3" />
                      </div>
                      <div>
                        <div className="flex items-center justify-between">
                          <span className="font-semibold text-xs text-slate-900 dark:text-slate-100">
                            2. Hybrid Retrieval & Reranking
                          </span>
                          <span className="text-[10px] font-mono text-slate-400">Standby</span>
                        </div>
                        <p className="text-[11px] text-slate-500 mt-0.5">
                          Dense vector + BM25Okapi + Reciprocal Rank Fusion + Neural Cross-Encoder
                        </p>
                      </div>
                    </div>

                    <div className="relative group">
                      <div className="absolute -left-6 top-0.5 flex h-5 w-5 items-center justify-center rounded-full bg-slate-300 text-slate-700 shadow-2xs ring-4 ring-white dark:bg-slate-700 dark:text-slate-300 dark:ring-slate-900">
                        <CheckCircle2 className="h-3 w-3" />
                      </div>
                      <div>
                        <div className="flex items-center justify-between">
                          <span className="font-semibold text-xs text-slate-900 dark:text-slate-100">
                            3. Evidence Assessment & Synthesis
                          </span>
                          <span className="text-[10px] font-mono text-slate-400">Standby</span>
                        </div>
                        <p className="text-[11px] text-slate-500 mt-0.5">
                          Topical evidence evaluation and grounded LLM generation
                        </p>
                      </div>
                    </div>
                  </>
                )}

                {/* Autonomous Recovery Standby Card */}
                <div className="relative group">
                  <div className="absolute -left-6 top-0.5 flex h-5 w-5 items-center justify-center rounded-full bg-slate-300 text-slate-700 shadow-2xs ring-4 ring-white dark:bg-slate-700 dark:text-slate-300 dark:ring-slate-900">
                    <Clock className="h-3 w-3" />
                  </div>
                  <div>
                    <div className="flex items-center justify-between">
                      <span className="font-semibold text-xs text-slate-900 dark:text-slate-100">
                        Autonomous Recovery
                      </span>
                      <Badge variant="outline" size="sm" className="text-[9px] py-0 px-1.5 text-slate-500">
                        {latestAssistantMessage?.retryCount && latestAssistantMessage.retryCount > 0
                          ? 'Bounded Retry Active'
                          : 'Standby (Adaptive)'}
                      </Badge>
                    </div>
                    <p className="text-[11px] text-slate-500 mt-0.5 leading-relaxed">
                      {latestAssistantMessage?.retryCount && latestAssistantMessage.retryCount > 0
                        ? `Executed ${latestAssistantMessage.retryCount} bounded retrieval retry under LangGraph.`
                        : 'Adaptive self-healing recovery loop actively monitors retrieval confidence and query ambiguity.'}
                    </p>
                  </div>
                </div>
              </div>
            </div>
          )}

          {/* TAB 2: SOURCES DETAIL */}
          {rightPanelTab === 'sources' && (
            <div className="space-y-3">
              <span className="text-xs font-bold text-slate-900 dark:text-slate-100 block">
                Retrieved Context Passages ({activeCitations.length})
              </span>
              {activeCitations.length === 0 ? (
                <div className="p-4 rounded-xl border border-slate-200 bg-slate-50 text-slate-500 text-xs text-center dark:bg-slate-800/40 dark:border-slate-800">
                  No evidence passages retrieved for the current response.
                </div>
              ) : (
                activeCitations.map((c) => (
                  <div
                    key={`${c.id}-${c.documentId || c.title}`}
                    className="p-3 rounded-xl border border-slate-200 bg-slate-50/50 space-y-2 dark:bg-slate-800/40 dark:border-slate-800"
                  >
                    <div className="flex items-center justify-between">
                      <span className="font-semibold text-xs text-slate-900 dark:text-slate-100 truncate">
                        [{c.id}] {c.title}
                      </span>
                      <span className="text-[10px] font-mono text-emerald-600 font-bold">
                        {c.relevanceScore != null
                          ? `${Math.round(c.relevanceScore * 100)}% match`
                          : 'Attributed'}
                      </span>
                    </div>
                    <p className="text-[11px] text-slate-600 dark:text-slate-400 italic line-clamp-3">
                      "{c.snippet}"
                    </p>
                    <div className="text-[10px] text-slate-500 flex justify-between pt-1">
                      <span>{c.page ? `Page ${c.page}` : 'Document chunk'}</span>
                      <span>{c.section || ''}</span>
                    </div>
                  </div>
                ))
              )}
            </div>
          )}

          {/* TAB 3: METADATA */}
          {rightPanelTab === 'metadata' && (
            <div className="space-y-3 text-xs">
              <span className="font-bold text-slate-900 dark:text-slate-100 block">
                Execution Telemetry
              </span>
              <div className="rounded-xl border border-slate-200 p-3 space-y-2 bg-slate-50/50 dark:bg-slate-800/40 dark:border-slate-800">
                <div className="flex justify-between">
                  <span className="text-slate-500">Selected KB</span>
                  <span className="font-mono font-medium truncate max-w-[150px]">
                    {selectedKb?.name || 'None'}
                  </span>
                </div>
                <div className="flex justify-between">
                  <span className="text-slate-500">Model Runtime</span>
                  <span className="font-mono font-medium">
                    {latestAssistantMessage?.model || 'grounded-synthesis'}
                  </span>
                </div>
                <div className="flex justify-between">
                  <span className="text-slate-500">Total Latency</span>
                  <span className="font-mono font-medium">
                    {latestAssistantMessage?.totalMs != null ? `${latestAssistantMessage.totalMs}ms` : '0ms'}
                  </span>
                </div>
                <div className="flex justify-between">
                  <span className="text-slate-500">Embedding Engine</span>
                  <span className="font-mono font-medium">FastEmbed bge-small-en</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-slate-500">Reranker Model</span>
                  <span className="font-mono font-medium">FlashRank TinyBERT</span>
                </div>
              </div>
            </div>
          )}
        </aside>
      )}

      {/* Citation Detail Inspector Drawer */}
      <Drawer
        open={selectedCitation !== null}
        onClose={() => setSelectedCitation(null)}
        title={
          selectedCitation ? (
            <div className="flex items-center gap-2">
              <FileText className="h-4 w-4 text-blue-600" />
              <span>Source [{selectedCitation.id}] Citation Inspector</span>
            </div>
          ) : undefined
        }
        description={selectedCitation?.title}
      >
        {selectedCitation && (
          <div className="space-y-4 text-xs">
            <div className="rounded-xl border border-slate-200 bg-slate-50 p-3.5 space-y-2 dark:bg-slate-800/50 dark:border-slate-800">
              <div className="flex items-center justify-between">
                <span className="text-slate-500 font-semibold">Document Title</span>
                <span className="font-medium text-slate-900 dark:text-slate-100">{selectedCitation.title}</span>
              </div>
              <div className="flex items-center justify-between">
                <span className="text-slate-500 font-semibold">Section & Page</span>
                <span className="font-mono text-slate-900 dark:text-slate-100">
                  {selectedCitation.section || 'N/A'}{selectedCitation.page ? ` · Page ${selectedCitation.page}` : ''}
                </span>
              </div>
              <div className="flex items-center justify-between">
                <span className="text-slate-500 font-semibold">Attribution Score</span>
                <span className="text-emerald-600 font-mono font-bold">
                  {selectedCitation.relevanceScore != null
                    ? `${Math.round(selectedCitation.relevanceScore * 100)}% Match`
                    : 'Attributed'}
                </span>
              </div>
            </div>

            <div>
              <div className="text-[11px] font-semibold uppercase tracking-wider text-slate-500 mb-1.5">
                Exact Extracted Knowledge Chunk
              </div>
              <blockquote className="rounded-xl border-l-3 border-blue-600 bg-white p-3.5 italic text-slate-700 shadow-2xs leading-relaxed dark:bg-slate-900 dark:text-slate-300">
                "{selectedCitation.snippet}"
              </blockquote>
            </div>

            <Button
              variant="outline"
              size="sm"
              onClick={() => {
                setSelectedCitation(null);
                navigate('/knowledge-base');
              }}
              className="w-full gap-2 text-xs border-blue-200 text-blue-600 hover:bg-blue-50"
            >
              <ExternalLink className="h-3.5 w-3.5" />
              <span>Manage in Knowledge Base</span>
            </Button>
          </div>
        )}
      </Drawer>
    </div>
  );
}
