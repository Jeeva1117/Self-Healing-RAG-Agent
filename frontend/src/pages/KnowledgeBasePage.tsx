import React, { useState, useId } from 'react';
import {
  BookOpen,
  Upload,
  FileText,
  Search,
  Trash2,
  FileSpreadsheet,
  FileCode,
  Layers,
  Plus,
  RefreshCw,
  AlertCircle,
  CheckCircle2,
  XCircle,
  Loader2,
  File,
  ChevronRight,
  Activity,
  Copy,
  GitBranch,
  Compass,
  Wrench,
} from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Badge } from '@/components/ui/badge';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table';
import { Modal } from '@/components/ui/modal';
import { Drawer } from '@/components/ui/drawer';
import { useToast } from '@/context/ToastContext';
import {
  useCreateKnowledgeBase,
  useDeleteDocument,
  useDeleteKnowledgeBase,
  useDocumentChunks,
  useDocuments,
  useKnowledgeBases,
  useReprocessDocument,
  useUploadDocument,
} from '@/hooks/useKnowledgeBase';
import type { DocumentItem, IngestionStatus } from '@/types/knowledgeBase';
import { KbHealthExplorer } from '@/components/knowledge-base/KbHealthExplorer';
import { KbDuplicateReview } from '@/components/knowledge-base/KbDuplicateReview';
import { KbVersioningView } from '@/components/knowledge-base/KbVersioningView';
import { KbCoverageInsights } from '@/components/knowledge-base/KbCoverageInsights';
import { KbRepairCenter } from '@/components/knowledge-base/KbRepairCenter';


const ALLOWED_EXTENSIONS = ['.pdf', '.docx', '.txt', '.md', '.csv', '.html', '.htm', '.json', '.xlsx'];
const MAX_FILE_SIZE_MB = 50;

function formatBytes(bytes: number, decimals = 1): string {
  if (bytes === 0) return '0 B';
  const k = 1024;
  const dm = decimals < 0 ? 0 : decimals;
  const sizes = ['B', 'KB', 'MB', 'GB'];
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  return `${parseFloat((bytes / Math.pow(k, i)).toFixed(dm))} ${sizes[i]}`;
}

function formatDate(isoString: string): string {
  try {
    const date = new Date(isoString);
    return date.toLocaleDateString('en-US', {
      month: 'short',
      day: 'numeric',
      year: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    });
  } catch {
    return isoString;
  }
}

function getFileIcon(filename: string) {
  const ext = filename.split('.').pop()?.toLowerCase();
  switch (ext) {
    case 'pdf':
      return <FileText className="w-4 h-4 text-rose-500" />;
    case 'docx':
      return <File className="w-4 h-4 text-blue-500" />;
    case 'csv':
    case 'xlsx':
      return <FileSpreadsheet className="w-4 h-4 text-emerald-500" />;
    case 'md':
    case 'html':
    case 'htm':
    case 'json':
      return <FileCode className="w-4 h-4 text-purple-500" />;
    case 'txt':
    default:
      return <FileText className="w-4 h-4 text-slate-500" />;
  }
}

export function KnowledgeBasePage() {
  const { toast } = useToast();
  const fileInputId = useId();

  // Knowledge Base State
  const { data: kbData, isLoading: isKbLoading } = useKnowledgeBases();
  const knowledgeBases = kbData?.items || [];
  const [selectedKbId, setSelectedKbId] = useState<string | null>(null);

  // Active Knowledge Base Resolution
  const activeKb =
    knowledgeBases.find((kb) => kb.id === selectedKbId) ||
    knowledgeBases[0] ||
    null;

  // Active KB Documents
  const {
    data: docData,
    isLoading: isDocsLoading,
    refetch: refetchDocs,
  } = useDocuments(activeKb?.id);
  const documents = docData?.items || [];

  // Mutations
  const createKbMutation = useCreateKnowledgeBase();
  const deleteKbMutation = useDeleteKnowledgeBase();
  const uploadDocMutation = useUploadDocument(activeKb?.id);
  const deleteDocMutation = useDeleteDocument(activeKb?.id);
  const reprocessDocMutation = useReprocessDocument(activeKb?.id);

  // UI Modals & State
  const [searchQuery, setSearchQuery] = useState('');
  const [isCreateKbOpen, setIsCreateKbOpen] = useState(false);
  const [kbName, setKbName] = useState('');
  const [kbDesc, setKbDesc] = useState('');
  const [activeTab, setActiveTab] = useState<
    'documents' | 'health' | 'duplicates' | 'versioning' | 'coverage' | 'repair'
  >('documents');
  const [repairTargetDocId, setRepairTargetDocId] = useState<string | null>(null);
  const [repairTargetAction, setRepairTargetAction] = useState<string | null>(null);

  const [isUploadModalOpen, setIsUploadModalOpen] = useState(false);
  const [dragOver, setDragOver] = useState(false);
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [uploadError, setUploadError] = useState<string | null>(null);

  const [selectedDoc, setSelectedDoc] = useState<DocumentItem | null>(null);
  const [isDrawerOpen, setIsDrawerOpen] = useState(false);

  // Document Chunks Query (for drawer view)
  const { data: chunksData, isLoading: isChunksLoading } = useDocumentChunks(
    selectedDoc?.id
  );
  const chunks = chunksData?.items || [];

  // Filtered Documents
  const filteredDocs = documents.filter((doc) =>
    doc.filename.toLowerCase().includes(searchQuery.toLowerCase())
  );

  // Handle Create Knowledge Base
  const handleCreateKb = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!kbName.trim()) return;
    try {
      const created = await createKbMutation.mutateAsync({
        name: kbName.trim(),
        description: kbDesc.trim() || undefined,
      });
      toast.success(`Created "${created.name}" successfully.`, 'Knowledge Base Created');
      setSelectedKbId(created.id);
      setIsCreateKbOpen(false);
      setKbName('');
      setKbDesc('');
    } catch (err: unknown) {
      toast.error(err instanceof Error ? err.message : 'Could not create knowledge base.', 'Creation Failed');
    }
  };

  // Handle Delete Knowledge Base
  const handleDeleteKb = async (kbId: string, name: string) => {
    if (!window.confirm(`Are you sure you want to delete "${name}" and all its ingested documents?`)) {
      return;
    }
    try {
      await deleteKbMutation.mutateAsync(kbId);
      toast.success(`Deleted "${name}" and associated chunks.`, 'Knowledge Base Deleted');
      setSelectedKbId(null);
    } catch (err: unknown) {
      toast.error(err instanceof Error ? err.message : 'Could not delete knowledge base.', 'Deletion Failed');
    }
  };

  // Validate File Selection
  const validateFile = (file: File): string | null => {
    const ext = '.' + file.name.split('.').pop()?.toLowerCase();
    if (!ALLOWED_EXTENSIONS.includes(ext)) {
      return `Unsupported format "${ext}". Supported formats: ${ALLOWED_EXTENSIONS.join(', ')}`;
    }
    if (file.size > MAX_FILE_SIZE_MB * 1024 * 1024) {
      return `File exceeds maximum size of ${MAX_FILE_SIZE_MB}MB (${formatBytes(file.size)}).`;
    }
    return null;
  };

  // Handle File Selection via Drag & Drop or File Picker
  const handleFileDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setDragOver(false);
    if (e.dataTransfer.files && e.dataTransfer.files[0]) {
      const file = e.dataTransfer.files[0];
      const error = validateFile(file);
      if (error) {
        setUploadError(error);
        setSelectedFile(null);
      } else {
        setUploadError(null);
        setSelectedFile(file);
      }
    }
  };

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files[0]) {
      const file = e.target.files[0];
      const error = validateFile(file);
      if (error) {
        setUploadError(error);
        setSelectedFile(null);
      } else {
        setUploadError(null);
        setSelectedFile(file);
      }
    }
  };

  // Handle Upload Document
  const handleUploadSubmit = async () => {
    if (!selectedFile || !activeKb) return;
    setUploadError(null);
    try {
      await uploadDocMutation.mutateAsync(selectedFile);
      toast.success(
        `Ingestion started for "${selectedFile.name}". Parsing, chunking, and embedding are now running.`,
        'Upload Accepted'
      );
      setIsUploadModalOpen(false);
      setSelectedFile(null);
      refetchDocs();
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Upload failed.';
      setUploadError(msg);
      toast.error(msg, 'Upload Failed');
    }
  };

  // Handle Delete Document
  const handleDeleteDocument = async (docId: string, filename: string) => {
    if (!window.confirm(`Delete document "${filename}" and its vector chunks?`)) {
      return;
    }
    try {
      await deleteDocMutation.mutateAsync(docId);
      toast.success(`Removed "${filename}".`, 'Document Deleted');
      if (selectedDoc?.id === docId) {
        setIsDrawerOpen(false);
        setSelectedDoc(null);
      }
    } catch (err: unknown) {
      toast.error(err instanceof Error ? err.message : 'Could not delete document.', 'Deletion Failed');
    }
  };

  // Handle Reprocess Document
  const handleReprocessDocument = async (docId: string, filename: string) => {
    try {
      await reprocessDocMutation.mutateAsync(docId);
      toast.info(`Re-indexing "${filename}". Existing chunks cleared and ingestion started.`, 'Reprocessing Started');
    } catch (err: unknown) {
      toast.error(err instanceof Error ? err.message : 'Could not reprocess document.', 'Reprocess Failed');
    }
  };

  const getStatusBadge = (status: IngestionStatus) => {
    switch (status) {
      case 'READY':
        return (
          <Badge variant="success" className="gap-1 font-medium bg-emerald-50 text-emerald-700 border-emerald-200">
            <CheckCircle2 className="w-3 h-3 text-emerald-600" />
            Ready
          </Badge>
        );
      case 'PROCESSING':
        return (
          <Badge variant="secondary" className="gap-1 animate-pulse font-medium bg-blue-100 text-blue-800 border-blue-200">
            <Loader2 className="w-3 h-3 animate-spin text-blue-600" />
            Processing
          </Badge>
        );
      case 'UPLOADED':
        return (
          <Badge variant="secondary" className="gap-1 font-medium bg-indigo-50 text-indigo-700 border-indigo-200">
            <Loader2 className="w-3 h-3 text-indigo-600 animate-spin" />
            Queued
          </Badge>
        );
      case 'OCR_REQUIRED':
        return (
          <Badge variant="outline" className="gap-1 font-medium bg-amber-50 text-amber-800 border-amber-300">
            <AlertCircle className="w-3 h-3 text-amber-600" />
            OCR Required
          </Badge>
        );
      case 'FAILED':
        return (
          <Badge variant="destructive" className="gap-1 font-medium">
            <XCircle className="w-3 h-3" />
            Failed
          </Badge>
        );
      default:
        return <Badge variant="outline">{status}</Badge>;
    }
  };

  return (
    <div className="space-y-6">
      {/* Page Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <div className="flex items-center gap-2">
            <h1 className="text-2xl font-bold text-slate-900 tracking-tight">
              Knowledge Base
            </h1>
            <Badge variant="outline" className="border-blue-200 text-blue-700 bg-blue-50">
              Enterprise Vector Corpus
            </Badge>
          </div>
          <p className="text-sm text-slate-500 mt-1">
            Manage document ingestion, structure-aware chunking, and 384d dense embeddings in pgvector.
          </p>
        </div>

        <div className="flex items-center gap-3">
          <Button
            variant="outline"
            onClick={() => setIsCreateKbOpen(true)}
            className="border-slate-300 text-slate-700 hover:bg-slate-50 font-medium"
          >
            <Plus className="w-4 h-4 mr-1.5" />
            New Knowledge Base
          </Button>

          <Button
            variant="default"
            disabled={!activeKb}
            onClick={() => {
              setUploadError(null);
              setSelectedFile(null);
              setIsUploadModalOpen(true);
            }}
            className="bg-blue-600 hover:bg-blue-700 font-medium shadow-sm"
          >
            <Upload className="w-4 h-4 mr-1.5" />
            Upload Document
          </Button>
        </div>
      </div>

      {/* Knowledge Base Switcher & Metric Cards */}
      {knowledgeBases.length > 0 && (
        <div className="bg-white border border-slate-200 rounded-xl p-4 shadow-sm space-y-4">
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
            <div className="flex items-center gap-3">
              <label htmlFor="kb-select" className="text-xs font-semibold uppercase tracking-wider text-slate-500">
                Active Knowledge Base:
              </label>
              <select
                id="kb-select"
                value={activeKb?.id || ''}
                onChange={(e) => setSelectedKbId(e.target.value)}
                className="bg-slate-50 border border-slate-300 text-slate-900 text-sm font-semibold rounded-lg px-3 py-1.5 focus:ring-2 focus:ring-blue-500 focus:outline-none"
              >
                {knowledgeBases.map((kb) => (
                  <option key={kb.id} value={kb.id}>
                    {kb.name} ({kb.document_count} docs)
                  </option>
                ))}
              </select>
            </div>

            {activeKb && (
              <div className="flex items-center gap-2">
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() => handleDeleteKb(activeKb.id, activeKb.name)}
                  className="text-rose-600 hover:text-rose-700 hover:bg-rose-50 h-8 text-xs font-medium"
                >
                  <Trash2 className="w-3.5 h-3.5 mr-1" />
                  Delete Knowledge Base
                </Button>
              </div>
            )}
          </div>

          {activeKb && (
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 pt-3 border-t border-slate-100">
              <div className="bg-slate-50 rounded-lg p-3">
                <span className="text-xs font-medium text-slate-500 block">Total Documents</span>
                <span className="text-xl font-bold text-slate-900 mt-0.5 block">
                  {activeKb.document_count}
                </span>
              </div>
              <div className="bg-slate-50 rounded-lg p-3">
                <span className="text-xs font-medium text-slate-500 block">Indexed Chunks</span>
                <span className="text-xl font-bold text-blue-600 mt-0.5 block">
                  {activeKb.total_chunks}
                </span>
              </div>
              <div className="bg-slate-50 rounded-lg p-3">
                <span className="text-xs font-medium text-slate-500 block">Embedding Model</span>
                <span className="text-xs font-bold text-slate-800 mt-1 block truncate">
                  BAAI/bge-small-en-v1.5
                </span>
              </div>
              <div className="bg-slate-50 rounded-lg p-3">
                <span className="text-xs font-medium text-slate-500 block">Vector Dimensions</span>
                <span className="text-xl font-bold text-slate-900 mt-0.5 block">384-d</span>
              </div>
            </div>
          )}
        </div>
      )}

      {/* Phase 12 Knowledge Base Management Sub-Tabs */}
      {activeKb && (
        <div className="flex border-b border-slate-200 gap-1 overflow-x-auto pb-px">
          <button
            type="button"
            onClick={() => setActiveTab('documents')}
            className={`flex items-center gap-2 px-4 py-2.5 text-xs font-semibold border-b-2 transition-colors whitespace-nowrap ${
              activeTab === 'documents'
                ? 'border-blue-600 text-blue-600 bg-blue-50/50'
                : 'border-transparent text-slate-500 hover:text-slate-800 hover:border-slate-300'
            }`}
          >
            <FileText className="w-3.5 h-3.5" />
            Documents ({documents.length})
          </button>

          <button
            type="button"
            onClick={() => setActiveTab('health')}
            className={`flex items-center gap-2 px-4 py-2.5 text-xs font-semibold border-b-2 transition-colors whitespace-nowrap ${
              activeTab === 'health'
                ? 'border-blue-600 text-blue-600 bg-blue-50/50'
                : 'border-transparent text-slate-500 hover:text-slate-800 hover:border-slate-300'
            }`}
          >
            <Activity className="w-3.5 h-3.5" />
            Health Explorer
          </button>

          <button
            type="button"
            onClick={() => setActiveTab('duplicates')}
            className={`flex items-center gap-2 px-4 py-2.5 text-xs font-semibold border-b-2 transition-colors whitespace-nowrap ${
              activeTab === 'duplicates'
                ? 'border-blue-600 text-blue-600 bg-blue-50/50'
                : 'border-transparent text-slate-500 hover:text-slate-800 hover:border-slate-300'
            }`}
          >
            <Copy className="w-3.5 h-3.5" />
            Duplicate Review
          </button>

          <button
            type="button"
            onClick={() => setActiveTab('versioning')}
            className={`flex items-center gap-2 px-4 py-2.5 text-xs font-semibold border-b-2 transition-colors whitespace-nowrap ${
              activeTab === 'versioning'
                ? 'border-blue-600 text-blue-600 bg-blue-50/50'
                : 'border-transparent text-slate-500 hover:text-slate-800 hover:border-slate-300'
            }`}
          >
            <GitBranch className="w-3.5 h-3.5" />
            Version Lineage
          </button>

          <button
            type="button"
            onClick={() => setActiveTab('coverage')}
            className={`flex items-center gap-2 px-4 py-2.5 text-xs font-semibold border-b-2 transition-colors whitespace-nowrap ${
              activeTab === 'coverage'
                ? 'border-blue-600 text-blue-600 bg-blue-50/50'
                : 'border-transparent text-slate-500 hover:text-slate-800 hover:border-slate-300'
            }`}
          >
            <Compass className="w-3.5 h-3.5" />
            Coverage & Gaps
          </button>

          <button
            type="button"
            onClick={() => setActiveTab('repair')}
            className={`flex items-center gap-2 px-4 py-2.5 text-xs font-semibold border-b-2 transition-colors whitespace-nowrap ${
              activeTab === 'repair'
                ? 'border-blue-600 text-blue-600 bg-blue-50/50'
                : 'border-transparent text-slate-500 hover:text-slate-800 hover:border-slate-300'
            }`}
          >
            <Wrench className="w-3.5 h-3.5" />
            Repair Center
          </button>
        </div>
      )}

      {/* Main Content Area */}
      {isKbLoading ? (
        <div className="bg-white border border-slate-200 rounded-xl p-16 text-center">
          <Loader2 className="w-8 h-8 text-blue-600 animate-spin mx-auto mb-3" />
          <p className="text-sm text-slate-600">Loading knowledge bases...</p>
        </div>
      ) : knowledgeBases.length === 0 ? (
        // Empty State: No Knowledge Bases
        <div className="bg-white border border-slate-200 rounded-xl p-12 text-center max-w-xl mx-auto shadow-sm">
          <div className="w-14 h-14 rounded-2xl bg-blue-50 text-blue-600 flex items-center justify-center mx-auto mb-4">
            <BookOpen className="w-7 h-7" />
          </div>
          <h3 className="text-lg font-bold text-slate-900">No knowledge bases yet</h3>
          <p className="text-sm text-slate-500 mt-1.5 leading-relaxed">
            Create your first Knowledge Base to organize documents, extract structured text, and generate
            dense vector embeddings stored in PostgreSQL with pgvector.
          </p>
          <Button
            variant="default"
            onClick={() => setIsCreateKbOpen(true)}
            className="mt-6 bg-blue-600 hover:bg-blue-700 font-medium"
          >
            <Plus className="w-4 h-4 mr-1.5" />
            Create Knowledge Base
          </Button>
        </div>
      ) : activeTab === 'health' && activeKb ? (
        <KbHealthExplorer
          kbId={activeKb.id}
          onOpenRepair={(docId, act) => {
            setRepairTargetDocId(docId);
            setRepairTargetAction(act);
            setActiveTab('repair');
          }}
        />
      ) : activeTab === 'duplicates' && activeKb ? (
        <KbDuplicateReview kbId={activeKb.id} />
      ) : activeTab === 'versioning' && activeKb ? (
        <KbVersioningView kbId={activeKb.id} documents={documents} onRefreshDocs={refetchDocs} />
      ) : activeTab === 'coverage' && activeKb ? (
        <KbCoverageInsights kbId={activeKb.id} />
      ) : activeTab === 'repair' && activeKb ? (
        <KbRepairCenter
          kbId={activeKb.id}
          documents={documents}
          preselectedDocId={repairTargetDocId}
          preselectedAction={repairTargetAction}
          onRepairCompleted={refetchDocs}
        />
      ) : isDocsLoading ? (

        <div className="bg-white border border-slate-200 rounded-xl p-16 text-center">
          <Loader2 className="w-8 h-8 text-blue-600 animate-spin mx-auto mb-3" />
          <p className="text-sm text-slate-600">Loading documents...</p>
        </div>
      ) : documents.length === 0 ? (
        // Empty State: No Documents in Active KB
        <div className="bg-white border border-slate-200 rounded-xl p-12 text-center max-w-xl mx-auto shadow-sm">
          <div className="w-14 h-14 rounded-2xl bg-indigo-50 text-indigo-600 flex items-center justify-center mx-auto mb-4">
            <Upload className="w-7 h-7" />
          </div>
          <h3 className="text-lg font-bold text-slate-900">No documents yet</h3>
          <p className="text-sm text-slate-500 mt-1.5 leading-relaxed">
            Upload your first document to &quot;{activeKb?.name}&quot;. The ingestion pipeline will parse pages,
            clean text, split intelligent chunks, and generate 384-dimensional dense embeddings.
          </p>
          <div className="flex flex-wrap justify-center gap-2 mt-4 text-xs text-slate-500">
            <span className="bg-slate-100 px-2.5 py-1 rounded-md font-mono">PDF</span>
            <span className="bg-slate-100 px-2.5 py-1 rounded-md font-mono">DOCX</span>
            <span className="bg-slate-100 px-2.5 py-1 rounded-md font-mono">TXT</span>
            <span className="bg-slate-100 px-2.5 py-1 rounded-md font-mono">Markdown</span>
            <span className="bg-slate-100 px-2.5 py-1 rounded-md font-mono">CSV</span>
          </div>
          <Button
            variant="default"
            onClick={() => {
              setUploadError(null);
              setSelectedFile(null);
              setIsUploadModalOpen(true);
            }}
            className="mt-6 bg-blue-600 hover:bg-blue-700 font-medium"
          >
            <Upload className="w-4 h-4 mr-1.5" />
            Upload your first document
          </Button>
        </div>
      ) : (
        // Document Table View
        <div className="bg-white border border-slate-200 rounded-xl shadow-sm overflow-hidden">
          {/* Table Toolbar */}
          <div className="p-4 border-b border-slate-200 flex flex-col sm:flex-row sm:items-center justify-between gap-3">
            <div className="relative flex-1 max-w-sm">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400" />
              <Input
                type="text"
                placeholder="Search documents by name..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="pl-9 h-9 text-sm rounded-lg border-slate-300"
              />
            </div>
            <div className="text-xs text-slate-500 font-medium">
              Showing {filteredDocs.length} of {documents.length} document{documents.length !== 1 ? 's' : ''}
            </div>
          </div>

          <Table>
            <TableHeader className="bg-slate-50">
              <TableRow>
                <TableHead className="font-semibold text-slate-700">Document Name</TableHead>
                <TableHead className="font-semibold text-slate-700">Format & Size</TableHead>
                <TableHead className="font-semibold text-slate-700">Ingestion Status</TableHead>
                <TableHead className="font-semibold text-slate-700">Chunks</TableHead>
                <TableHead className="font-semibold text-slate-700">Uploaded</TableHead>
                <TableHead className="text-right font-semibold text-slate-700">Actions</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {filteredDocs.map((doc) => (
                <TableRow
                  key={doc.id}
                  className="hover:bg-slate-50/70 transition-colors cursor-pointer"
                  onClick={() => {
                    setSelectedDoc(doc);
                    setIsDrawerOpen(true);
                  }}
                >
                  <TableCell>
                    <div className="flex items-center gap-2.5">
                      <div className="p-1.5 bg-slate-100 rounded-md">
                        {getFileIcon(doc.filename)}
                      </div>
                      <div>
                        <span className="font-semibold text-slate-900 hover:text-blue-600 transition-colors block text-sm">
                          {doc.original_filename}
                        </span>
                        <span className="text-xs text-slate-400 font-mono truncate max-w-[200px] block">
                          SHA256: {doc.checksum.substring(0, 10)}...
                        </span>
                      </div>
                    </div>
                  </TableCell>

                  <TableCell>
                    <div className="text-sm font-medium text-slate-700 uppercase">
                      {doc.filename.split('.').pop()}
                    </div>
                    <div className="text-xs text-slate-500">{formatBytes(doc.file_size)}</div>
                  </TableCell>

                  <TableCell>
                    <div className="flex items-center gap-2">
                      {getStatusBadge(doc.status)}
                      {(doc.status === 'FAILED' || doc.status === 'OCR_REQUIRED') && doc.ingestion_error && (
                        <span
                          className={`text-xs truncate max-w-[140px] ${doc.status === 'OCR_REQUIRED' ? 'text-amber-700' : 'text-rose-600'}`}
                          title={doc.ingestion_error}
                        >
                          {doc.ingestion_error}
                        </span>
                      )}
                    </div>
                  </TableCell>

                  <TableCell>
                    {doc.status === 'READY' ? (
                      <span className="inline-flex items-center gap-1 font-semibold text-blue-700 bg-blue-50 px-2 py-0.5 rounded text-xs">
                        <Layers className="w-3 h-3" />
                        {doc.chunk_count}
                      </span>
                    ) : (
                      <span className="text-xs text-slate-400">-</span>
                    )}
                  </TableCell>

                  <TableCell className="text-xs text-slate-600">
                    {formatDate(doc.created_at)}
                  </TableCell>

                  <TableCell className="text-right" onClick={(e) => e.stopPropagation()}>
                    <div className="flex items-center justify-end gap-1">
                      <Button
                        variant="ghost"
                        size="sm"
                        title="Reprocess Document"
                        onClick={() => handleReprocessDocument(doc.id, doc.original_filename)}
                        className="h-8 w-8 p-0 text-slate-500 hover:text-blue-600"
                      >
                        <RefreshCw className="w-3.5 h-3.5" />
                      </Button>
                      <Button
                        variant="ghost"
                        size="sm"
                        title="Delete Document"
                        onClick={() => handleDeleteDocument(doc.id, doc.original_filename)}
                        className="h-8 w-8 p-0 text-slate-500 hover:text-rose-600"
                      >
                        <Trash2 className="w-3.5 h-3.5" />
                      </Button>
                      <Button
                        variant="ghost"
                        size="sm"
                        title="View Details"
                        onClick={() => {
                          setSelectedDoc(doc);
                          setIsDrawerOpen(true);
                        }}
                        className="h-8 w-8 p-0 text-slate-500 hover:text-slate-800"
                      >
                        <ChevronRight className="w-4 h-4" />
                      </Button>
                    </div>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </div>
      )}

      {/* Modal: Create Knowledge Base */}
      <Modal
        open={isCreateKbOpen}
        onClose={() => setIsCreateKbOpen(false)}
        title="Create Knowledge Base"
        description="Organize your documents into a dedicated vector collection."
      >
        <form onSubmit={handleCreateKb} className="space-y-4">
          <div>
            <label htmlFor="kb-name-input" className="block text-xs font-semibold text-slate-700 uppercase tracking-wider mb-1.5">
              Knowledge Base Name *
            </label>
            <Input
              id="kb-name-input"
              type="text"
              required
              placeholder="e.g., Engineering Architecture, Legal & Policies"
              value={kbName}
              onChange={(e) => setKbName(e.target.value)}
              className="rounded-lg text-sm"
            />
          </div>

          <div>
            <label htmlFor="kb-desc-input" className="block text-xs font-semibold text-slate-700 uppercase tracking-wider mb-1.5">
              Description (Optional)
            </label>
            <Input
              id="kb-desc-input"
              type="text"
              placeholder="Brief summary of document domain or team ownership"
              value={kbDesc}
              onChange={(e) => setKbDesc(e.target.value)}
              className="rounded-lg text-sm"
            />
          </div>

          <div className="flex justify-end gap-2 pt-2">
            <Button
              type="button"
              variant="outline"
              onClick={() => setIsCreateKbOpen(false)}
            >
              Cancel
            </Button>
            <Button
              type="submit"
              variant="default"
              disabled={createKbMutation.isPending || !kbName.trim()}
              className="bg-blue-600 hover:bg-blue-700"
            >
              {createKbMutation.isPending && (
                <Loader2 className="w-4 h-4 mr-1.5 animate-spin" />
              )}
              Create Knowledge Base
            </Button>
          </div>
        </form>
      </Modal>

      {/* Modal: Upload Document */}
      <Modal
        open={isUploadModalOpen}
        onClose={() => {
          if (!uploadDocMutation.isPending) {
            setIsUploadModalOpen(false);
          }
        }}
        title={`Upload to "${activeKb?.name}"`}
        description="Select or drag and drop a document. Ingestion and embedding run asynchronously."
      >
        <div className="space-y-4">
          {/* Drag & Drop Area */}
          <div
            onDragOver={(e) => {
              e.preventDefault();
              setDragOver(true);
            }}
            onDragLeave={() => setDragOver(false)}
            onDrop={handleFileDrop}
            className={`border-2 border-dashed rounded-xl p-8 text-center transition-all ${
              dragOver
                ? 'border-blue-500 bg-blue-50/60'
                : 'border-slate-300 bg-slate-50/50 hover:bg-slate-50'
            }`}
          >
            <Upload className="w-10 h-10 text-slate-400 mx-auto mb-2" />
            <p className="text-sm font-semibold text-slate-700">
              Drag & drop your file here, or{' '}
              <label
                htmlFor={fileInputId}
                className="text-blue-600 hover:underline cursor-pointer"
              >
                browse
              </label>
            </p>
            <input
              id={fileInputId}
              type="file"
              accept=".pdf,.docx,.txt,.md,.csv,.html,.htm,.json,.xlsx"
              onChange={handleFileChange}
              className="hidden"
            />
            <p className="text-xs text-slate-400 mt-2">
              Supported formats: PDF, DOCX, TXT, Markdown, CSV, HTML, JSON, XLSX (up to 50MB)
            </p>
          </div>

          {/* Selected File Details */}
          {selectedFile && (
            <div className="bg-blue-50 border border-blue-200 rounded-lg p-3 flex items-center justify-between">
              <div className="flex items-center gap-2.5 truncate">
                {getFileIcon(selectedFile.name)}
                <div className="truncate">
                  <span className="text-sm font-semibold text-blue-950 block truncate">
                    {selectedFile.name}
                  </span>
                  <span className="text-xs text-blue-700">
                    {formatBytes(selectedFile.size)}
                  </span>
                </div>
              </div>
              <Button
                variant="ghost"
                size="sm"
                onClick={() => setSelectedFile(null)}
                className="text-blue-700 hover:text-blue-900 h-7 px-2 text-xs"
              >
                Change
              </Button>
            </div>
          )}

          {/* Error Message */}
          {uploadError && (
            <div className="bg-rose-50 border border-rose-200 text-rose-800 rounded-lg p-3 text-xs flex items-start gap-2">
              <AlertCircle className="w-4 h-4 text-rose-600 shrink-0 mt-0.5" />
              <span>{uploadError}</span>
            </div>
          )}

          <div className="flex justify-end gap-2 pt-2">
            <Button
              type="button"
              variant="outline"
              disabled={uploadDocMutation.isPending}
              onClick={() => setIsUploadModalOpen(false)}
            >
              Cancel
            </Button>
            <Button
              type="button"
              variant="default"
              disabled={!selectedFile || uploadDocMutation.isPending}
              onClick={handleUploadSubmit}
              className="bg-blue-600 hover:bg-blue-700"
            >
              {uploadDocMutation.isPending && (
                <Loader2 className="w-4 h-4 mr-1.5 animate-spin" />
              )}
              {uploadDocMutation.isPending ? 'Uploading & Queuing...' : 'Start Ingestion'}
            </Button>
          </div>
        </div>
      </Modal>

      {/* Drawer: Document Details & Chunks Viewer */}
      <Drawer
        open={isDrawerOpen}
        onClose={() => setIsDrawerOpen(false)}
        title={selectedDoc?.original_filename || 'Document Details'}
      >
        {selectedDoc && (
          <div className="space-y-6 text-sm">
            {/* Status & Actions Bar */}
            <div className="flex items-center justify-between p-3.5 bg-slate-50 border border-slate-200 rounded-xl">
              <div>
                <span className="text-xs font-semibold uppercase tracking-wider text-slate-500 block">
                  Status
                </span>
                <div className="mt-1">{getStatusBadge(selectedDoc.status)}</div>
              </div>
              <div className="flex items-center gap-2">
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() =>
                    handleReprocessDocument(selectedDoc.id, selectedDoc.original_filename)
                  }
                  className="text-xs font-medium"
                >
                  <RefreshCw className="w-3.5 h-3.5 mr-1" />
                  Reprocess
                </Button>
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() =>
                    handleDeleteDocument(selectedDoc.id, selectedDoc.original_filename)
                  }
                  className="text-xs font-medium text-rose-600 hover:text-rose-700 hover:bg-rose-50"
                >
                  <Trash2 className="w-3.5 h-3.5 mr-1" />
                  Delete
                </Button>
              </div>
            </div>

            {/* Error Banner if Failed */}
            {selectedDoc.status === 'FAILED' && selectedDoc.ingestion_error && (
              <div className="p-3.5 bg-rose-50 border border-rose-200 rounded-xl text-rose-900 text-xs flex items-start gap-2.5">
                <AlertCircle className="w-4 h-4 text-rose-600 shrink-0 mt-0.5" />
                <div>
                  <span className="font-semibold block">Ingestion Error</span>
                  <span className="mt-0.5 block">{selectedDoc.ingestion_error}</span>
                </div>
              </div>
            )}

            {/* Document Metadata Grid */}
            <div className="space-y-3">
              <h4 className="text-xs font-bold uppercase tracking-wider text-slate-600">
                Metadata & Storage
              </h4>
              <div className="grid grid-cols-2 gap-2.5 text-xs">
                <div className="p-2.5 bg-slate-50 rounded-lg">
                  <span className="text-slate-400 block">File Size</span>
                  <span className="font-semibold text-slate-800 mt-0.5 block">
                    {formatBytes(selectedDoc.file_size)}
                  </span>
                </div>
                <div className="p-2.5 bg-slate-50 rounded-lg">
                  <span className="text-slate-400 block">MIME Type</span>
                  <span className="font-semibold text-slate-800 mt-0.5 block truncate">
                    {selectedDoc.content_type}
                  </span>
                </div>
                <div className="p-2.5 bg-slate-50 rounded-lg">
                  <span className="text-slate-400 block">Version</span>
                  <span className="font-semibold text-slate-800 mt-0.5 block">
                    v{selectedDoc.active_version}
                  </span>
                </div>
                <div className="p-2.5 bg-slate-50 rounded-lg">
                  <span className="text-slate-400 block">Total Chunks</span>
                  <span className="font-semibold text-blue-600 mt-0.5 block">
                    {selectedDoc.chunk_count}
                  </span>
                </div>
              </div>
              <div className="p-2.5 bg-slate-50 rounded-lg text-xs space-y-1">
                <div className="text-slate-400">SHA-256 Checksum:</div>
                <div className="font-mono text-slate-800 break-all select-all">
                  {selectedDoc.checksum}
                </div>
              </div>
            </div>

            {/* Real Chunks List */}
            <div className="space-y-3">
              <div className="flex items-center justify-between">
                <h4 className="text-xs font-bold uppercase tracking-wider text-slate-600 flex items-center gap-1.5">
                  <Layers className="w-4 h-4 text-blue-600" />
                  Indexed Chunks ({chunks.length})
                </h4>
                <span className="text-[11px] font-mono text-slate-400">
                  Model: BAAI/bge-small-en-v1.5
                </span>
              </div>

              {isChunksLoading ? (
                <div className="py-8 text-center text-xs text-slate-500">
                  <Loader2 className="w-5 h-5 animate-spin mx-auto mb-2 text-blue-600" />
                  Loading chunks...
                </div>
              ) : chunks.length === 0 ? (
                <div className="p-6 text-center text-xs text-slate-400 bg-slate-50 rounded-lg border border-dashed border-slate-200">
                  {selectedDoc.status === 'PROCESSING'
                    ? 'Chunks are currently being generated and embedded...'
                    : 'No chunks available for this document.'}
                </div>
              ) : (
                <div className="space-y-2.5 max-h-[380px] overflow-y-auto pr-1">
                  {chunks.map((chunk) => (
                    <div
                      key={chunk.id}
                      className="p-3 border border-slate-200 rounded-lg bg-white shadow-2xs hover:border-blue-300 transition-colors"
                    >
                      <div className="flex items-center justify-between text-[11px] text-slate-500 mb-1.5">
                        <span className="font-mono font-bold text-blue-700">
                          Chunk #{chunk.chunk_index + 1}
                        </span>
                        <div className="flex items-center gap-2">
                          {chunk.page_number && (
                            <span className="bg-slate-100 px-1.5 py-0.5 rounded text-slate-700 font-medium">
                              Page {chunk.page_number}
                            </span>
                          )}
                          {chunk.section_title && (
                            <span className="bg-slate-100 px-1.5 py-0.5 rounded text-slate-700 font-medium truncate max-w-[120px]">
                              {chunk.section_title}
                            </span>
                          )}
                          <span className="text-slate-400">
                            {chunk.token_count || '~'} tokens ({chunk.character_count} chars)
                          </span>
                        </div>
                      </div>
                      <p className="text-xs text-slate-800 font-mono bg-slate-50 p-2 rounded border border-slate-100 leading-relaxed max-h-24 overflow-y-auto whitespace-pre-wrap select-all">
                        {chunk.content}
                      </p>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>
        )}
      </Drawer>
    </div>
  );
}
