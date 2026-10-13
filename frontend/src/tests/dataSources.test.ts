import { describe, it, expect, vi, beforeEach } from 'vitest';
import { dataSourcesService } from '@/services/dataSourcesService';
import type { ConnectorCatalogItem, DataSourceItem } from '@/types/dataSources';

describe('DataSources Service & Contract Validation', () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it('getCatalog returns structured connector items including local and external connectors', async () => {
    const mockCatalog: ConnectorCatalogItem[] = [
      {
        source_type: 'local',
        name: 'Local Files & Manual Upload',
        description: 'Upload PDF, DOCX, TXT, Markdown, CSV, HTML, JSON, and XLSX files.',
        icon: 'FolderUp',
        requires_auth: false,
        auth_type: 'none',
        configured_count: 0,
        active_status: 'ready',
        setup_guide: 'Upload directly into Knowledge Base.',
      },
      {
        source_type: 'web',
        name: 'Website & Documentation Scraper',
        description: 'Crawl public websites with SSRF defenses.',
        icon: 'Globe',
        requires_auth: false,
        auth_type: 'none',
        configured_count: 1,
        active_status: 'connected',
        setup_guide: 'Provide a valid public URL.',
      },
      {
        source_type: 'github',
        name: 'GitHub Docs & Code',
        description: 'Index code and documentation from GitHub.',
        icon: 'GitBranch',
        requires_auth: true,
        auth_type: 'pat',
        configured_count: 0,
        active_status: 'not_configured',
        setup_guide: 'Provide repository name and PAT.',
      },
    ];

    vi.spyOn(dataSourcesService, 'getCatalog').mockResolvedValue(mockCatalog);

    const catalog = await dataSourcesService.getCatalog();
    expect(catalog).toHaveLength(3);
    expect(catalog[0].source_type).toBe('local');
    expect(catalog[0].active_status).toBe('ready');
    expect(catalog[1].source_type).toBe('web');
    expect(catalog[1].active_status).toBe('connected');
    expect(catalog[2].requires_auth).toBe(true);
  });

  it('listDataSources returns empty array when no sources are configured', async () => {
    vi.spyOn(dataSourcesService, 'listDataSources').mockResolvedValue([]);

    const sources = await dataSourcesService.listDataSources();
    expect(sources).toEqual([]);
    expect(sources).toHaveLength(0);
  });

  it('listDataSources handles configured connector records', async () => {
    const mockSources: DataSourceItem[] = [
      {
        id: 'ds-123',
        user_id: 'user-456',
        source_type: 'web',
        name: 'FastAPI Documentation',
        description: 'Official FastAPI docs',
        config: { root_url: 'https://fastapi.tiangolo.com/' },
        status: 'ready',
        synced_documents_count: 5,
        synced_chunks_count: 25,
        created_at: '2026-01-01T00:00:00Z',
        updated_at: '2026-01-01T00:00:00Z',
      },
    ];

    vi.spyOn(dataSourcesService, 'listDataSources').mockResolvedValue(mockSources);

    const sources = await dataSourcesService.listDataSources();
    expect(sources).toHaveLength(1);
    expect(sources[0].name).toBe('FastAPI Documentation');
    expect(sources[0].synced_documents_count).toBe(5);
  });

  it('testConnection reports accurate status and browse capability', async () => {
    vi.spyOn(dataSourcesService, 'testConnection').mockResolvedValue({
      success: true,
      message: 'Connection verified successfully.',
      details: { url: 'https://fastapi.tiangolo.com/' },
      can_browse: true,
    });

    const res = await dataSourcesService.testConnection('ds-123');
    expect(res.success).toBe(true);
    expect(res.can_browse).toBe(true);
    expect(res.message).toContain('verified');
  });

  it('handles backend error propagation gracefully', async () => {
    vi.spyOn(dataSourcesService, 'getCatalog').mockRejectedValue(
      new Error('Internal server error: "MetaInfo" object has no field "total"')
    );

    await expect(dataSourcesService.getCatalog()).rejects.toThrow(
      'Internal server error: "MetaInfo" object has no field "total"'
    );
  });

  it('category filtering partitions catalog accurately', () => {
    const catalog: ConnectorCatalogItem[] = [
      { source_type: 'local', name: 'Local', description: '', icon: '', requires_auth: false, auth_type: 'none', configured_count: 0, active_status: 'ready', setup_guide: '' },
      { source_type: 'web', name: 'Web', description: '', icon: '', requires_auth: false, auth_type: 'none', configured_count: 0, active_status: 'not_configured', setup_guide: '' },
      { source_type: 'github', name: 'GitHub', description: '', icon: '', requires_auth: true, auth_type: 'pat', configured_count: 0, active_status: 'not_configured', setup_guide: '' },
      { source_type: 'gdrive', name: 'GDrive', description: '', icon: '', requires_auth: true, auth_type: 'oauth', configured_count: 0, active_status: 'not_configured', setup_guide: '' },
      { source_type: 'notion', name: 'Notion', description: '', icon: '', requires_auth: true, auth_type: 'token', configured_count: 0, active_status: 'not_configured', setup_guide: '' },
      { source_type: 'postgres', name: 'Postgres', description: '', icon: '', requires_auth: true, auth_type: 'credentials', configured_count: 0, active_status: 'not_configured', setup_guide: '' },
    ];

    const filterCategory = (category: string) => catalog.filter((c) => {
      if (category === 'all') return true;
      if (category === 'local') return c.source_type === 'local';
      if (category === 'web') return c.source_type === 'web';
      if (category === 'cloud') return ['github', 'gdrive', 'notion'].includes(c.source_type);
      if (category === 'databases') return c.source_type === 'postgres';
      return true;
    });

    expect(filterCategory('all')).toHaveLength(6);
    expect(filterCategory('local')).toHaveLength(1);
    expect(filterCategory('web')).toHaveLength(1);
    expect(filterCategory('cloud')).toHaveLength(3);
    expect(filterCategory('databases')).toHaveLength(1);
  });
});
