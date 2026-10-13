import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  FolderUp,
  Globe,
  Database,
  GitBranch,
  HardDrive,
  Share2,
  CheckCircle2,
  AlertCircle,
  RefreshCw,
  Plus,
  Trash2,
  ShieldCheck,
  ArrowRight,
  Sliders,
  Sparkles,
  AlertTriangle,
} from 'lucide-react';
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Modal } from '@/components/ui/modal';
import { Input } from '@/components/ui/input';
import { useToast } from '@/context/ToastContext';
import { dataSourcesService } from '@/services/dataSourcesService';
import { knowledgeBaseService } from '@/services/knowledgeBaseService';
import type {
  ConnectionTestResult,
  ConnectorCatalogItem,
  DataSourceItem,
  DataSourceStatus,
  DataSourceType,
  SourceItem,
  SyncResult,
} from '@/types/dataSources';
import type { KnowledgeBase } from '@/types/knowledgeBase';

interface ConfigModalState {
  open: boolean;
  type: DataSourceType;
  title: string;
  sourceItem?: DataSourceItem;
}

interface BrowseModalState {
  open: boolean;
  sourceItem?: DataSourceItem;
}

export function DataSourcesPage() {
  const navigate = useNavigate();
  const { toast } = useToast();
  const [activeCategory, setActiveCategory] = useState<string>('all');
  const [catalog, setCatalog] = useState<ConnectorCatalogItem[]>([]);
  const [sources, setSources] = useState<DataSourceItem[]>([]);
  const [knowledgeBases, setKnowledgeBases] = useState<KnowledgeBase[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  // Active configure modal state
  const [configModal, setConfigModal] = useState<ConfigModalState>({
    open: false,
    type: 'web',
    title: '',
  });

  // Browse & sync modal state
  const [browseModal, setBrowseModal] = useState<BrowseModalState>({
    open: false,
  });

  // Config form state
  const [formData, setFormData] = useState<{
    name: string;
    description: string;
    knowledge_base_id: string;
    config: Record<string, any>;
  }>({
    name: '',
    description: '',
    knowledge_base_id: '',
    config: {},
  });

  // Test connection state
  const [testing, setTesting] = useState<boolean>(false);
  const [testResult, setTestResult] = useState<ConnectionTestResult | null>(null);

  // Browsing items state
  const [browsing, setBrowsing] = useState<boolean>(false);
  const [browseItems, setBrowseItems] = useState<SourceItem[]>([]);
  const [selectedItemIds, setSelectedItemIds] = useState<string[]>([]);
  const [targetKbId, setTargetKbId] = useState<string>('');

  // Syncing state
  const [syncing, setSyncing] = useState<boolean>(false);
  const [syncResult, setSyncResult] = useState<SyncResult | null>(null);

  const loadData = async () => {
    try {
      setLoading(true);
      setError(null);
      const [catRes, srcRes, kbRes] = await Promise.all([
        dataSourcesService.getCatalog(),
        dataSourcesService.listDataSources(),
        knowledgeBaseService.listKnowledgeBases(0, 50).catch(() => ({ items: [], total: 0 })),
      ]);
      setCatalog(catRes);
      setSources(srcRes);
      setKnowledgeBases(kbRes.items || []);
    } catch (err: any) {
      const errMsg = err?.message || 'Failed to connect to backend server';
      setError(errMsg);
      toast.error(`Failed to load data sources: ${errMsg}`);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadData();
  }, []);

  const getConnectorIcon = (type: string) => {
    switch (type) {
      case 'web':
        return Globe;
      case 'github':
        return GitBranch;
      case 'gdrive':
        return HardDrive;
      case 'notion':
        return Share2;
      case 'postgres':
        return Database;
      default:
        return FolderUp;
    }
  };

  const getStatusBadge = (status: DataSourceStatus | 'configured') => {
    switch (status) {
      case 'ready':
      case 'configured':
        return (
          <Badge variant="success" size="sm" className="gap-1 bg-emerald-50 text-emerald-700 border-emerald-200 dark:bg-emerald-950/40 dark:text-emerald-400 dark:border-emerald-800">
            <CheckCircle2 className="h-3 w-3" />
            <span>Ready</span>
          </Badge>
        );
      case 'connected':
        return (
          <Badge variant="default" size="sm" className="gap-1 bg-blue-50 text-blue-700 border-blue-200 dark:bg-blue-950/40 dark:text-blue-400 dark:border-blue-800">
            <CheckCircle2 className="h-3 w-3" />
            <span>Connected</span>
          </Badge>
        );
      case 'syncing':
        return (
          <Badge variant="warning" size="sm" className="gap-1 animate-pulse bg-amber-50 text-amber-700 border-amber-200 dark:bg-amber-950/40 dark:text-amber-400 dark:border-amber-800">
            <RefreshCw className="h-3 w-3 animate-spin" />
            <span>Syncing</span>
          </Badge>
        );
      case 'setup_required':
        return (
          <Badge variant="outline" size="sm" className="gap-1 text-orange-600 bg-orange-50 border-orange-200 dark:bg-orange-950/40 dark:text-orange-400 dark:border-orange-800">
            <AlertCircle className="h-3 w-3" />
            <span>Setup Required</span>
          </Badge>
        );
      case 'partial_failure':
        return (
          <Badge variant="warning" size="sm" className="gap-1 bg-amber-50 text-amber-700 border-amber-200 dark:bg-amber-950/40 dark:text-amber-400 dark:border-amber-800">
            <AlertCircle className="h-3 w-3" />
            <span>Partial Failure</span>
          </Badge>
        );
      case 'disconnected':
        return (
          <Badge variant="outline" size="sm" className="gap-1 text-slate-500 bg-slate-50 border-slate-200 dark:bg-slate-800/40 dark:text-slate-400 dark:border-slate-700">
            <AlertCircle className="h-3 w-3" />
            <span>Disconnected</span>
          </Badge>
        );
      case 'failed':
        return (
          <Badge variant="destructive" size="sm" className="gap-1">
            <AlertCircle className="h-3 w-3" />
            <span>Failed</span>
          </Badge>
        );
      default:
        return (
          <Badge variant="outline" size="sm" className="text-slate-500 bg-slate-50 border-slate-200 dark:bg-slate-800/40 dark:text-slate-400 dark:border-slate-700">
            Not Configured
          </Badge>
        );
    }
  };

  const handleOpenConfig = (item: ConnectorCatalogItem, existingSource?: DataSourceItem) => {
    if (item.source_type === 'local') {
      navigate('/knowledge-base');
      return;
    }

    const defaultKb = knowledgeBases.length > 0 ? knowledgeBases[0].id : '';

    if (existingSource) {
      setFormData({
        name: existingSource.name,
        description: existingSource.description || '',
        knowledge_base_id: existingSource.knowledge_base_id || defaultKb,
        config: { ...existingSource.config },
      });
      setConfigModal({
        open: true,
        type: existingSource.source_type,
        title: `Configure ${existingSource.name}`,
        sourceItem: existingSource,
      });
    } else {
      // Default template configs
      let initialConfig: Record<string, any> = {};
      let initialName = item.name;

      if (item.source_type === 'web') {
        initialConfig = {
          root_url: 'https://docs.python.org/3/',
          max_pages: 10,
          max_depth: 2,
        };
        initialName = 'Python 3 Documentation';
      } else if (item.source_type === 'github') {
        initialConfig = {
          repository: 'groq/groq-python',
          branch: 'main',
          personal_access_token: '',
          allowed_extensions: ['md', 'py', 'txt'],
        };
        initialName = 'GitHub Docs & Code';
      } else if (item.source_type === 'gdrive') {
        initialConfig = {
          access_token: '',
          folder_id: '',
          client_id: '',
        };
        initialName = 'Team Google Drive';
      } else if (item.source_type === 'notion') {
        initialConfig = {
          integration_token: '',
        };
        initialName = 'Engineering Notion Wiki';
      } else if (item.source_type === 'postgres') {
        initialConfig = {
          host: '127.0.0.1',
          port: 5432,
          database: 'external_analytics',
          user: 'readonly_user',
          password: '',
          schema: 'public',
          max_rows: 50,
          allow_self_connect: false,
        };
        initialName = 'Analytics PostgreSQL';
      }

      setFormData({
        name: initialName,
        description: `Connected ${item.name} for RAG retrieval`,
        knowledge_base_id: defaultKb,
        config: initialConfig,
      });

      setConfigModal({
        open: true,
        type: item.source_type,
        title: `Connect ${item.name}`,
      });
    }
    setTestResult(null);
  };

  const handleSaveConfig = async () => {
    try {
      if (!formData.name.trim()) {
        toast.error('Please specify a connection name');
        return;
      }

      let saved: DataSourceItem;
      if (configModal.sourceItem) {
        saved = await dataSourcesService.updateDataSource(configModal.sourceItem.id, {
          name: formData.name,
          description: formData.description,
          knowledge_base_id: formData.knowledge_base_id || null,
          config: formData.config,
        });
        toast.success(`Updated ${saved.name}`);
      } else {
        saved = await dataSourcesService.createDataSource({
          source_type: configModal.type,
          name: formData.name,
          description: formData.description,
          knowledge_base_id: formData.knowledge_base_id || null,
          config: formData.config,
        });
        toast.success(`Configured ${saved.name}`);
      }

      setConfigModal({ open: false, type: 'web', title: '' });
      await loadData();
    } catch (err: any) {
      toast.error(`Error saving connector: ${err.message}`);
    }
  };

  const handleTestConnection = async (sourceId: string) => {
    try {
      setTesting(true);
      setTestResult(null);
      const res = await dataSourcesService.testConnection(sourceId);
      setTestResult(res);
      if (res.success) {
        toast.success(`Connection verified: ${res.message}`);
      } else {
        toast.warning(res.message);
      }
      await loadData();
    } catch (err: any) {
      toast.error(`Test failed: ${err.message}`);
      setTestResult({
        success: false,
        message: err.message,
        details: {},
        can_browse: false,
      });
    } finally {
      setTesting(false);
    }
  };

  const handleOpenBrowse = async (source: DataSourceItem) => {
    setBrowseModal({
      open: true,
      sourceItem: source,
    });
    setTargetKbId(source.knowledge_base_id || (knowledgeBases.length > 0 ? knowledgeBases[0].id : ''));
    setBrowseItems([]);
    setSelectedItemIds([]);
    setSyncResult(null);

    try {
      setBrowsing(true);
      const items = await dataSourcesService.listSourceItems(source.id);
      setBrowseItems(items);
      // Auto-select all selectable items
      setSelectedItemIds(items.filter((i) => i.selectable).map((i) => i.id));
    } catch (err: any) {
      toast.error(`Failed to browse items: ${err.message}`);
    } finally {
      setBrowsing(false);
    }
  };

  const handleTriggerSync = async () => {
    if (!browseModal.sourceItem) return;
    if (selectedItemIds.length === 0) {
      toast.warning('Please select at least one item to index');
      return;
    }
    if (!targetKbId) {
      toast.warning('Please choose a target Knowledge Base');
      return;
    }

    try {
      setSyncing(true);
      setSyncResult(null);
      const res = await dataSourcesService.syncDataSource(browseModal.sourceItem.id, {
        selected_ids: selectedItemIds,
        knowledge_base_id: targetKbId,
      });
      setSyncResult(res);
      if (res.success) {
        toast.success(`Successfully ingested ${res.documents_created} documents (${res.chunks_created} vector chunks)`);
      } else {
        toast.warning(`Ingestion finished with ${res.errors.length} notices`);
      }
      await loadData();
    } catch (err: any) {
      toast.error(`Sync failed: ${err.message}`);
    } finally {
      setSyncing(false);
    }
  };

  const handleDeleteSource = async (sourceId: string, name: string) => {
    if (!confirm(`Are you sure you want to disconnect and delete ${name}?`)) return;
    try {
      await dataSourcesService.deleteDataSource(sourceId);
      toast.success(`Disconnected ${name}`);
      await loadData();
    } catch (err: any) {
      toast.error(`Failed to delete: ${err.message}`);
    }
  };

  const filteredCatalog = catalog.filter((c) => {
    if (activeCategory === 'all') return true;
    if (activeCategory === 'local') return c.source_type === 'local';
    if (activeCategory === 'web') return c.source_type === 'web';
    if (activeCategory === 'cloud') return ['github', 'gdrive', 'notion'].includes(c.source_type);
    if (activeCategory === 'databases') return c.source_type === 'postgres';
    return true;
  });

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <div className="flex items-center gap-2">
            <h1 className="text-2xl font-bold tracking-tight text-slate-100 light:text-slate-900">
              Data Sources & External Connectors
            </h1>
            <Badge variant="outline" className="gap-1 border-blue-500/30 text-blue-400 bg-blue-500/10">
              <Sparkles className="h-3 w-3" />
              <span>Full RAG Pipeline</span>
            </Badge>
          </div>
          <p className="text-xs sm:text-sm text-slate-400 light:text-slate-500 mt-1">
            Connect live websites, Git repositories, databases, and enterprise cloud docs directly into pgvector embeddings.
          </p>
        </div>

        <Button
          variant="outline"
          size="sm"
          onClick={loadData}
          disabled={loading}
          className="gap-1.5 self-start sm:self-auto border-slate-700 hover:bg-slate-800"
        >
          <RefreshCw className={`h-3.5 w-3.5 ${loading ? 'animate-spin' : ''}`} />
          <span>Refresh</span>
        </Button>
      </div>

      {/* Security Banner */}
      <div className="rounded-xl border border-blue-500/20 bg-blue-950/20 p-4 text-xs text-blue-200/90 dark:border-blue-900/50 flex items-start gap-3">
        <ShieldCheck className="h-5 w-5 text-blue-400 shrink-0 mt-0.5" />
        <div>
          <p className="font-semibold text-blue-300">Enterprise Security & Isolation Controls Active</p>
          <p className="text-slate-400 mt-0.5 leading-relaxed">
            All external connectors enforce SSRF defenses against private RFC 1918 subnets and cloud metadata endpoints, strict SQL injection parameterization, secret stripping (.env, keys), read-only database connections, and tenant data isolation.
          </p>
        </div>
      </div>

      {/* Filter Tabs */}
      <div className="flex items-center gap-1.5 p-1 rounded-lg border border-slate-800 bg-slate-900/60 max-w-fit light:bg-slate-100 light:border-slate-200">
        {['all', 'local', 'web', 'cloud', 'databases'].map((cat) => (
          <button
            key={cat}
            onClick={() => setActiveCategory(cat)}
            className={`px-3 py-1 rounded-md text-xs font-medium capitalize transition-colors cursor-pointer ${
              activeCategory === cat
                ? 'bg-blue-600 text-white shadow-sm'
                : 'text-slate-400 hover:text-slate-200 light:text-slate-600'
            }`}
          >
            {cat}
          </button>
        ))}
      </div>

      {/* Error State with Retry */}
      {error && !loading && (
        <Card className="rounded-2xl border-rose-900/50 bg-rose-950/20 p-6 text-rose-200">
          <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
            <div className="flex items-start gap-3">
              <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-rose-500/20 text-rose-400 border border-rose-500/30">
                <AlertTriangle className="h-5 w-5" />
              </div>
              <div>
                <h3 className="font-semibold text-rose-100 text-sm">Failed to Load Data Sources</h3>
                <p className="text-xs text-rose-300/80 mt-1 leading-relaxed">
                  {error}
                </p>
                <p className="text-[11px] text-slate-400 mt-1">
                  Ensure the backend service is running and healthy. You can retry the connection below.
                </p>
              </div>
            </div>
            <Button
              variant="default"
              size="sm"
              onClick={loadData}
              className="gap-2 bg-rose-600 hover:bg-rose-500 text-white shrink-0 cursor-pointer"
            >
              <RefreshCw className="h-3.5 w-3.5" />
              <span>Retry</span>
            </Button>
          </div>
        </Card>
      )}

      {/* Loading Skeleton Grid */}
      {loading && (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {[1, 2, 3, 4, 5, 6].map((idx) => (
            <Card
              key={idx}
              className="rounded-2xl border-slate-800 bg-slate-900/40 p-5 space-y-4 animate-pulse"
            >
              <div className="flex items-center justify-between">
                <div className="h-10 w-10 rounded-xl bg-slate-800" />
                <div className="h-5 w-16 rounded-full bg-slate-800" />
              </div>
              <div className="space-y-2">
                <div className="h-4 w-3/4 rounded bg-slate-800" />
                <div className="h-3 w-full rounded bg-slate-800/60" />
                <div className="h-3 w-5/6 rounded bg-slate-800/60" />
              </div>
              <div className="pt-2 border-t border-slate-800 flex justify-end">
                <div className="h-8 w-28 rounded bg-slate-800" />
              </div>
            </Card>
          ))}
        </div>
      )}

      {/* Empty State */}
      {!loading && !error && filteredCatalog.length === 0 && (
        <Card className="rounded-2xl border-slate-800 bg-slate-900/60 p-12 text-center">
          <div className="flex h-12 w-12 mx-auto items-center justify-center rounded-xl bg-slate-800 text-slate-400 mb-3 border border-slate-700">
            <FolderUp className="h-6 w-6" />
          </div>
          <h3 className="font-semibold text-slate-200 text-base">No Data Sources Found</h3>
          <p className="text-xs text-slate-400 mt-1 max-w-sm mx-auto">
            {activeCategory === 'all'
              ? 'No connector definitions are currently registered in the catalog.'
              : `No connectors match the category "${activeCategory}".`}
          </p>
          {activeCategory !== 'all' && (
            <Button
              variant="outline"
              size="sm"
              onClick={() => setActiveCategory('all')}
              className="mt-4 text-xs border-slate-700 hover:bg-slate-800 cursor-pointer"
            >
              Show All Connectors
            </Button>
          )}
        </Card>
      )}

      {/* Catalog Grid */}
      {!loading && !error && filteredCatalog.length > 0 && (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {filteredCatalog.map((item) => {
            const Icon = getConnectorIcon(item.source_type);
            const configuredForType = sources.filter((s) => s.source_type === item.source_type);
            const activeSource = configuredForType.length > 0 ? configuredForType[0] : null;
            const status = activeSource ? (activeSource.status as DataSourceStatus) : item.active_status;

            return (
              <Card
                key={item.source_type}
                className="flex flex-col justify-between rounded-2xl border-slate-800 bg-slate-900/90 shadow-sm hover:border-blue-500/40 hover:shadow-md transition-all light:bg-white light:border-slate-200"
              >
                <CardHeader className="pb-3">
                  <div className="flex items-start justify-between gap-2 mb-2">
                    <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-blue-500/10 text-blue-400 border border-blue-500/20 light:bg-blue-50 light:text-blue-600">
                      <Icon className="h-5 w-5" />
                    </div>
                    {getStatusBadge(status)}
                  </div>

                  <CardTitle className="text-base font-semibold text-slate-100 light:text-slate-900">
                    {item.name}
                  </CardTitle>
                  <CardDescription className="text-xs mt-1 text-slate-400 light:text-slate-500 leading-relaxed">
                    {item.description}
                  </CardDescription>

                  {activeSource && (
                    <div className="mt-3 pt-2 border-t border-slate-800/80 text-[11px] text-slate-400 space-y-1">
                      <div className="flex justify-between">
                        <span className="text-slate-500">Active Name:</span>
                        <span className="font-medium text-slate-300">{activeSource.name}</span>
                      </div>
                      {activeSource.synced_documents_count > 0 && (
                        <div className="flex justify-between">
                          <span className="text-slate-500">Synced Corpus:</span>
                          <span className="font-medium text-emerald-400">
                            {activeSource.synced_documents_count} docs ({activeSource.synced_chunks_count} chunks)
                          </span>
                        </div>
                      )}
                      {activeSource.last_sync_error && (
                        <div className="text-rose-400/90 line-clamp-2 mt-1">
                          Notice: {activeSource.last_sync_error}
                        </div>
                      )}
                    </div>
                  )}
                </CardHeader>

                <CardContent className="pt-2 border-t border-slate-800/60 light:border-slate-100 flex items-center justify-between gap-2">
                  {activeSource ? (
                    <>
                      <div className="flex items-center gap-1.5">
                        <Button
                          variant="outline"
                          size="xs"
                          onClick={() => handleOpenConfig(item, activeSource)}
                          className="gap-1 text-xs border-slate-700 hover:bg-slate-800 text-slate-300 cursor-pointer"
                        >
                          <Sliders className="h-3 w-3" />
                          <span>Config</span>
                        </Button>
                        <Button
                          variant="ghost"
                          size="xs"
                          onClick={() => handleDeleteSource(activeSource.id, activeSource.name)}
                          className="text-xs text-rose-400 hover:text-rose-300 hover:bg-rose-950/30 cursor-pointer"
                        >
                          <Trash2 className="h-3 w-3" />
                        </Button>
                      </div>

                      <div className="flex items-center gap-1.5">
                        <Button
                          variant="outline"
                          size="xs"
                          onClick={() => handleTestConnection(activeSource.id)}
                          disabled={testing}
                          className="gap-1 text-xs border-blue-500/30 text-blue-400 hover:bg-blue-500/10 cursor-pointer"
                        >
                          <RefreshCw className={`h-3 w-3 ${testing ? 'animate-spin' : ''}`} />
                          <span>Test</span>
                        </Button>
                        <Button
                          variant="default"
                          size="xs"
                          onClick={() => handleOpenBrowse(activeSource)}
                          className="gap-1 text-xs bg-blue-600 hover:bg-blue-500 text-white font-medium cursor-pointer"
                        >
                          <span>Sync</span>
                          <ArrowRight className="h-3 w-3" />
                        </Button>
                      </div>
                    </>
                  ) : (
                    <Button
                      variant="default"
                      size="xs"
                      onClick={() => handleOpenConfig(item)}
                      className="w-full gap-1.5 text-xs bg-blue-600 hover:bg-blue-500 text-white font-medium justify-center cursor-pointer"
                    >
                      <Plus className="h-3.5 w-3.5" />
                      <span>{item.source_type === 'local' ? 'Open Knowledge Base' : 'Configure Connector'}</span>
                    </Button>
                  )}
                </CardContent>
              </Card>
            );
          })}
        </div>
      )}

      {/* Configuration Modal */}
      <Modal
        open={configModal.open}
        onClose={() => setConfigModal({ open: false, type: 'web', title: '' })}
        title={configModal.title}
        maxWidth="lg"
      >
        <div className="space-y-4 text-xs">
          {/* Target Knowledge Base */}
          <div>
            <label className="block text-slate-300 font-medium mb-1">Target Knowledge Base</label>
            <select
              value={formData.knowledge_base_id}
              onChange={(e) => setFormData({ ...formData, knowledge_base_id: e.target.value })}
              className="w-full rounded-md border border-slate-700 bg-slate-800 px-3 py-1.5 text-slate-100 focus:outline-none focus:ring-1 focus:ring-blue-500"
            >
              <option value="">-- Select Knowledge Base --</option>
              {knowledgeBases.map((kb) => (
                <option key={kb.id} value={kb.id}>
                  {kb.name} ({kb.status})
                </option>
              ))}
            </select>
          </div>

          {/* Connection Name */}
          <div>
            <label className="block text-slate-300 font-medium mb-1">Connection Name</label>
            <Input
              value={formData.name}
              onChange={(e) => setFormData({ ...formData, name: e.target.value })}
              placeholder="e.g. Production Docs"
              className="bg-slate-800 border-slate-700 text-slate-100"
            />
          </div>

          {/* Specific Connector Forms */}
          {configModal.type === 'web' && (
            <div className="space-y-3 p-3 rounded-lg bg-slate-800/60 border border-slate-700/60">
              <div className="flex items-center gap-2 text-blue-400 font-medium">
                <Globe className="h-4 w-4" />
                <span>Web Scraper Configuration</span>
              </div>
              <div>
                <label className="block text-slate-300 mb-1">Public Documentation / Root URL</label>
                <Input
                  value={formData.config.root_url || ''}
                  onChange={(e) =>
                    setFormData({
                      ...formData,
                      config: { ...formData.config, root_url: e.target.value },
                    })
                  }
                  placeholder="https://docs.python.org/3/"
                  className="bg-slate-900 border-slate-700 text-slate-100"
                />
                <p className="text-[11px] text-slate-400 mt-1">
                  Private IP ranges (127.0.0.1, 10.x, 192.168.x, 169.254.169.254) are rejected by SSRF guardrails.
                </p>
              </div>
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-slate-300 mb-1">Max Pages to Crawl</label>
                  <Input
                    type="number"
                    min="1"
                    max="50"
                    value={formData.config.max_pages || 10}
                    onChange={(e) =>
                      setFormData({
                        ...formData,
                        config: { ...formData.config, max_pages: parseInt(e.target.value) || 10 },
                      })
                    }
                    className="bg-slate-900 border-slate-700 text-slate-100"
                  />
                </div>
                <div>
                  <label className="block text-slate-300 mb-1">Crawl Depth</label>
                  <Input
                    type="number"
                    min="1"
                    max="3"
                    value={formData.config.max_depth || 2}
                    onChange={(e) =>
                      setFormData({
                        ...formData,
                        config: { ...formData.config, max_depth: parseInt(e.target.value) || 1 },
                      })
                    }
                    className="bg-slate-900 border-slate-700 text-slate-100"
                  />
                </div>
              </div>
            </div>
          )}

          {configModal.type === 'github' && (
            <div className="space-y-3 p-3 rounded-lg bg-slate-800/60 border border-slate-700/60">
              <div className="flex items-center gap-2 text-blue-400 font-medium">
                <GitBranch className="h-4 w-4" />
                <span>GitHub Repository Configuration</span>
              </div>
              <div>
                <label className="block text-slate-300 mb-1">Repository (owner/name)</label>
                <Input
                  value={formData.config.repository || ''}
                  onChange={(e) =>
                    setFormData({
                      ...formData,
                      config: { ...formData.config, repository: e.target.value },
                    })
                  }
                  placeholder="e.g. groq/groq-python"
                  className="bg-slate-900 border-slate-700 text-slate-100"
                />
              </div>
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-slate-300 mb-1">Branch</label>
                  <Input
                    value={formData.config.branch || 'main'}
                    onChange={(e) =>
                      setFormData({
                        ...formData,
                        config: { ...formData.config, branch: e.target.value },
                      })
                    }
                    placeholder="main"
                    className="bg-slate-900 border-slate-700 text-slate-100"
                  />
                </div>
                <div>
                  <label className="block text-slate-300 mb-1">Personal Access Token (optional for public)</label>
                  <Input
                    type="password"
                    value={formData.config.personal_access_token || ''}
                    onChange={(e) =>
                      setFormData({
                        ...formData,
                        config: { ...formData.config, personal_access_token: e.target.value },
                      })
                    }
                    placeholder="ghp_..."
                    className="bg-slate-900 border-slate-700 text-slate-100"
                  />
                </div>
              </div>
              <p className="text-[11px] text-slate-400">
                Secrets (.env, *.pem, *.key) and node_modules are automatically filtered out during ingestion.
              </p>
            </div>
          )}

          {configModal.type === 'gdrive' && (
            <div className="space-y-3 p-3 rounded-lg bg-slate-800/60 border border-slate-700/60">
              <div className="flex items-center gap-2 text-blue-400 font-medium">
                <HardDrive className="h-4 w-4" />
                <span>Google Drive Integration</span>
              </div>
              <div>
                <label className="block text-slate-300 mb-1">OAuth Access Token / Service Bearer Token</label>
                <Input
                  type="password"
                  value={formData.config.access_token || ''}
                  onChange={(e) =>
                    setFormData({
                      ...formData,
                      config: { ...formData.config, access_token: e.target.value },
                    })
                  }
                  placeholder="ya29.a0... (OAuth Access Token)"
                  className="bg-slate-900 border-slate-700 text-slate-100"
                />
              </div>
              <div>
                <label className="block text-slate-300 mb-1">Google OAuth Client ID / Service Key (Optional)</label>
                <Input
                  value={formData.config.client_id || ''}
                  onChange={(e) =>
                    setFormData({
                      ...formData,
                      config: { ...formData.config, client_id: e.target.value },
                    })
                  }
                  placeholder="e.g. 123456789-apps.googleusercontent.com"
                  className="bg-slate-900 border-slate-700 text-slate-100"
                />
              </div>
              <div>
                <label className="block text-slate-300 mb-1">Folder ID (optional to restrict scope)</label>
                <Input
                  value={formData.config.folder_id || ''}
                  onChange={(e) =>
                    setFormData({
                      ...formData,
                      config: { ...formData.config, folder_id: e.target.value },
                    })
                  }
                  placeholder="Root or specific Drive Folder ID"
                  className="bg-slate-900 border-slate-700 text-slate-100"
                />
              </div>
              <p className="text-[11px] text-amber-300/90">
                Requires OAuth credentials authorized with the drive.readonly scope. If credentials are not yet generated, connection test will provide full setup prerequisites.
              </p>
            </div>
          )}

          {configModal.type === 'notion' && (
            <div className="space-y-3 p-3 rounded-lg bg-slate-800/60 border border-slate-700/60">
              <div className="flex items-center gap-2 text-blue-400 font-medium">
                <Share2 className="h-4 w-4" />
                <span>Notion Integration Token</span>
              </div>
              <div>
                <label className="block text-slate-300 mb-1">Internal Integration Secret</label>
                <Input
                  type="password"
                  value={formData.config.integration_token || ''}
                  onChange={(e) =>
                    setFormData({
                      ...formData,
                      config: { ...formData.config, integration_token: e.target.value },
                    })
                  }
                  placeholder="secret_..."
                  className="bg-slate-900 border-slate-700 text-slate-100"
                />
              </div>
              <p className="text-[11px] text-slate-400">
                Create an integration at <span className="font-mono text-blue-400">notion.so/my-integrations</span> and share target workspace pages with your integration bot.
              </p>
            </div>
          )}

          {configModal.type === 'postgres' && (
            <div className="space-y-3 p-3 rounded-lg bg-slate-800/60 border border-slate-700/60">
              <div className="flex items-center gap-2 text-blue-400 font-medium">
                <Database className="h-4 w-4" />
                <span>PostgreSQL Read-Only Connection</span>
              </div>
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-slate-300 mb-1">Host</label>
                  <Input
                    value={formData.config.host || '127.0.0.1'}
                    onChange={(e) =>
                      setFormData({
                        ...formData,
                        config: { ...formData.config, host: e.target.value },
                      })
                    }
                    placeholder="127.0.0.1"
                    className="bg-slate-900 border-slate-700 text-slate-100"
                  />
                </div>
                <div>
                  <label className="block text-slate-300 mb-1">Port</label>
                  <Input
                    type="number"
                    value={formData.config.port || 5432}
                    onChange={(e) =>
                      setFormData({
                        ...formData,
                        config: { ...formData.config, port: parseInt(e.target.value) || 5432 },
                      })
                    }
                    placeholder="5432"
                    className="bg-slate-900 border-slate-700 text-slate-100"
                  />
                </div>
              </div>
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-slate-300 mb-1">Database</label>
                  <Input
                    value={formData.config.database || ''}
                    onChange={(e) =>
                      setFormData({
                        ...formData,
                        config: { ...formData.config, database: e.target.value },
                      })
                    }
                    placeholder="production_db"
                    className="bg-slate-900 border-slate-700 text-slate-100"
                  />
                </div>
                <div>
                  <label className="block text-slate-300 mb-1">Schema</label>
                  <Input
                    value={formData.config.schema || 'public'}
                    onChange={(e) =>
                      setFormData({
                        ...formData,
                        config: { ...formData.config, schema: e.target.value },
                      })
                    }
                    placeholder="public"
                    className="bg-slate-900 border-slate-700 text-slate-100"
                  />
                </div>
              </div>
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-slate-300 mb-1">Username</label>
                  <Input
                    value={formData.config.user || ''}
                    onChange={(e) =>
                      setFormData({
                        ...formData,
                        config: { ...formData.config, user: e.target.value },
                      })
                    }
                    placeholder="readonly_reader"
                    className="bg-slate-900 border-slate-700 text-slate-100"
                  />
                </div>
                <div>
                  <label className="block text-slate-300 mb-1">Password</label>
                  <Input
                    type="password"
                    value={formData.config.password || ''}
                    onChange={(e) =>
                      setFormData({
                        ...formData,
                        config: { ...formData.config, password: e.target.value },
                      })
                    }
                    placeholder="******"
                    className="bg-slate-900 border-slate-700 text-slate-100"
                  />
                </div>
              </div>
              <p className="text-[11px] text-slate-400">
                To prevent accidental loops, connections to the application's internal database are blocked by default.
              </p>
              <div className="flex items-center gap-2 pt-1">
                <input
                  type="checkbox"
                  id="allow_self_connect"
                  checked={Boolean(formData.config.allow_self_connect)}
                  onChange={(e) =>
                    setFormData({
                      ...formData,
                      config: { ...formData.config, allow_self_connect: e.target.checked },
                    })
                  }
                  className="rounded border-slate-700 text-blue-600 focus:ring-blue-500 bg-slate-900 cursor-pointer"
                />
                <label htmlFor="allow_self_connect" className="text-slate-300 text-[11px] cursor-pointer">
                  Allow connection to local instance (bypasses loop block for authorized tests)
                </label>
              </div>
            </div>
          )}

          {/* Test connection feedback */}
          {testResult && (
            <div
              className={`p-3 rounded-lg border text-xs ${
                testResult.success
                  ? 'border-emerald-500/30 bg-emerald-950/20 text-emerald-300'
                  : 'border-orange-500/30 bg-orange-950/20 text-orange-300'
              }`}
            >
              <div className="flex items-center gap-2 font-semibold">
                {testResult.success ? <CheckCircle2 className="h-4 w-4" /> : <AlertCircle className="h-4 w-4" />}
                <span>{testResult.success ? 'Verification Passed' : 'Prerequisite / Setup Notice'}</span>
              </div>
              <p className="mt-1 leading-relaxed">{testResult.message}</p>
            </div>
          )}

          {/* Footer Actions */}
          <div className="flex items-center justify-end gap-2 pt-3 border-t border-slate-800">
            <Button
              variant="outline"
              size="sm"
              onClick={() => setConfigModal({ open: false, type: 'web', title: '' })}
              className="border-slate-700 hover:bg-slate-800"
            >
              Cancel
            </Button>
            <Button
              variant="default"
              size="sm"
              onClick={handleSaveConfig}
              className="bg-blue-600 hover:bg-blue-500 text-white font-medium"
            >
              Save Connector
            </Button>
          </div>
        </div>
      </Modal>

      {/* Item Discovery & Synchronization Modal */}
      <Modal
        open={browseModal.open}
        onClose={() => setBrowseModal({ open: false })}
        title={`Sync ${browseModal.sourceItem?.name || 'Data Source'}`}
        maxWidth="lg"
      >
        <div className="space-y-4 text-xs">
          {/* Target Knowledge Base Selection */}
          <div>
            <label className="block text-slate-300 font-medium mb-1">Index Into Knowledge Base</label>
            <select
              value={targetKbId}
              onChange={(e) => setTargetKbId(e.target.value)}
              className="w-full rounded-md border border-slate-700 bg-slate-800 px-3 py-1.5 text-slate-100 focus:outline-none focus:ring-1 focus:ring-blue-500"
            >
              {knowledgeBases.map((kb) => (
                <option key={kb.id} value={kb.id}>
                  {kb.name} ({kb.status})
                </option>
              ))}
            </select>
          </div>

          {/* Discovered Items List */}
          <div>
            <div className="flex items-center justify-between mb-1.5">
              <span className="text-slate-300 font-medium">
                Discovered Sources ({browseItems.length} found)
              </span>
              <div className="flex items-center gap-2">
                <button
                  type="button"
                  onClick={() => setSelectedItemIds(browseItems.filter((i) => i.selectable).map((i) => i.id))}
                  className="text-blue-400 hover:text-blue-300 cursor-pointer"
                >
                  Select All
                </button>
                <span className="text-slate-600">|</span>
                <button
                  type="button"
                  onClick={() => setSelectedItemIds([])}
                  className="text-slate-400 hover:text-slate-300 cursor-pointer"
                >
                  Clear
                </button>
              </div>
            </div>

            {browsing ? (
              <div className="flex flex-col items-center justify-center p-8 border border-slate-800 rounded-lg bg-slate-900/50 space-y-2">
                <RefreshCw className="h-6 w-6 text-blue-400 animate-spin" />
                <p className="text-slate-400">Discovering and validating accessible sources...</p>
              </div>
            ) : browseItems.length === 0 ? (
              <div className="p-6 border border-slate-800 rounded-lg bg-slate-900/50 text-center text-slate-400">
                <AlertCircle className="h-6 w-6 text-amber-400 mx-auto mb-2" />
                <p>No selectable items were discovered with current credentials.</p>
                <p className="text-[11px] text-slate-500 mt-1">
                  Ensure the external URL or credentials are valid and have permissions to read resources.
                </p>
              </div>
            ) : (
              <div className="max-h-60 overflow-y-auto space-y-1.5 p-2 rounded-lg border border-slate-800 bg-slate-900/60">
                {browseItems.map((item) => {
                  const isChecked = selectedItemIds.includes(item.id);
                  return (
                    <label
                      key={item.id}
                      className={`flex items-center justify-between p-2 rounded-md border cursor-pointer transition-colors ${
                        isChecked
                          ? 'border-blue-500/40 bg-blue-950/20 text-slate-100'
                          : 'border-slate-800 bg-slate-800/30 text-slate-400 hover:bg-slate-800/60'
                      }`}
                    >
                      <div className="flex items-center gap-2.5 overflow-hidden">
                        <input
                          type="checkbox"
                          checked={isChecked}
                          onChange={(e) => {
                            if (e.target.checked) {
                              setSelectedItemIds([...selectedItemIds, item.id]);
                            } else {
                              setSelectedItemIds(selectedItemIds.filter((id) => id !== item.id));
                            }
                          }}
                          className="rounded border-slate-700 bg-slate-800 text-blue-600 focus:ring-0"
                        />
                        <div className="truncate">
                          <p className="font-medium truncate">{item.name}</p>
                          <p className="text-[10px] text-slate-500 font-mono truncate">{item.url || item.path || item.id}</p>
                        </div>
                      </div>
                      <Badge variant="outline" size="sm" className="shrink-0 text-[10px]">
                        {item.item_type}
                      </Badge>
                    </label>
                  );
                })}
              </div>
            )}
          </div>

          {/* Sync Result Feedback */}
          {syncResult && (
            <div
              className={`p-3 rounded-lg border text-xs ${
                syncResult.success
                  ? 'border-emerald-500/30 bg-emerald-950/20 text-emerald-300'
                  : 'border-amber-500/30 bg-amber-950/20 text-amber-300'
              }`}
            >
              <div className="flex items-center gap-2 font-semibold">
                <CheckCircle2 className="h-4 w-4" />
                <span>Ingestion Completed</span>
              </div>
              <p className="mt-1">
                Indexed <span className="font-bold">{syncResult.documents_created}</span> documents, created{' '}
                <span className="font-bold">{syncResult.chunks_created}</span> dense pgvector chunks.
              </p>
              {syncResult.errors.length > 0 && (
                <div className="mt-2 text-rose-400">
                  <p className="font-semibold">Errors encountered:</p>
                  <ul className="list-disc pl-4 space-y-0.5 mt-1">
                    {syncResult.errors.map((e, idx) => (
                      <li key={idx}>{e}</li>
                    ))}
                  </ul>
                </div>
              )}
            </div>
          )}

          {/* Modal Actions */}
          <div className="flex items-center justify-between pt-3 border-t border-slate-800">
            <span className="text-[11px] text-slate-400">
              {selectedItemIds.length} of {browseItems.length} selected
            </span>
            <div className="flex items-center gap-2">
              <Button
                variant="outline"
                size="sm"
                onClick={() => setBrowseModal({ open: false })}
                className="border-slate-700 hover:bg-slate-800"
              >
                Close
              </Button>
              <Button
                variant="default"
                size="sm"
                onClick={handleTriggerSync}
                disabled={syncing || selectedItemIds.length === 0}
                className="gap-1.5 bg-blue-600 hover:bg-blue-500 text-white font-medium"
              >
                <RefreshCw className={`h-3.5 w-3.5 ${syncing ? 'animate-spin' : ''}`} />
                <span>{syncing ? 'Ingesting into RAG...' : 'Sync Selected Now'}</span>
              </Button>
            </div>
          </div>
        </div>
      </Modal>
    </div>
  );
}
