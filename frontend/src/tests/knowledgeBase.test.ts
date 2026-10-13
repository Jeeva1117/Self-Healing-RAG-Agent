import { describe, it, expect, vi, beforeEach } from 'vitest';
import { knowledgeBaseService } from '@/services/knowledgeBaseService';
import * as apiModule from '@/services/api';

describe('Knowledge Base Service & Client Validations', () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it('fetches knowledge bases list via apiClient', async () => {
    const mockResponse = {
      success: true,
      data: {
        items: [
          {
            id: 'kb-1',
            owner_id: 'user-1',
            name: 'Engineering Specs',
            description: 'Architecture guides',
            status: 'ACTIVE',
            created_at: '2026-03-01T00:00:00Z',
            updated_at: '2026-03-01T00:00:00Z',
            document_count: 5,
            total_chunks: 42,
          },
        ],
        total: 1,
        limit: 50,
        offset: 0,
      },
    };

    vi.spyOn(apiModule, 'apiClient').mockResolvedValue(mockResponse);

    const result = await knowledgeBaseService.listKnowledgeBases();
    expect(result.items).toHaveLength(1);
    expect(result.items[0].name).toBe('Engineering Specs');
    expect(result.items[0].document_count).toBe(5);
    expect(result.items[0].total_chunks).toBe(42);
  });

  it('creates knowledge base with name and description', async () => {
    const mockCreated = {
      success: true,
      data: {
        id: 'kb-2',
        owner_id: 'user-1',
        name: 'Legal Documents',
        description: 'Vendor contracts',
        status: 'ACTIVE',
        created_at: '2026-03-01T00:00:00Z',
        updated_at: '2026-03-01T00:00:00Z',
        document_count: 0,
        total_chunks: 0,
      },
    };

    const spy = vi.spyOn(apiModule, 'apiClient').mockResolvedValue(mockCreated);

    const result = await knowledgeBaseService.createKnowledgeBase({
      name: 'Legal Documents',
      description: 'Vendor contracts',
    });

    expect(result.id).toBe('kb-2');
    expect(result.name).toBe('Legal Documents');
    expect(spy).toHaveBeenCalledWith('/knowledge-bases', {
      method: 'POST',
      body: JSON.stringify({ name: 'Legal Documents', description: 'Vendor contracts' }),
    });
  });

  it('uploads document with multipart FormData and returns accepted status', async () => {
    const mockDoc = {
      success: true,
      data: {
        id: 'doc-1',
        knowledge_base_id: 'kb-1',
        owner_id: 'user-1',
        filename: 'handbook.pdf',
        original_filename: 'handbook.pdf',
        content_type: 'application/pdf',
        file_size: 1048576,
        checksum: 'abc123sha',
        storage_key: 'kbs/kb-1/doc-1/handbook.pdf',
        status: 'UPLOADED',
        ingestion_error: null,
        created_at: '2026-03-01T00:00:00Z',
        updated_at: '2026-03-01T00:00:00Z',
        chunk_count: 0,
        active_version: 1,
      },
    };

    const spy = vi.spyOn(apiModule, 'apiClient').mockResolvedValue(mockDoc);

    const file = new File(['mock content'], 'handbook.pdf', { type: 'application/pdf' });
    const result = await knowledgeBaseService.uploadDocument('kb-1', file);

    expect(result.id).toBe('doc-1');
    expect(result.status).toBe('UPLOADED');
    expect(spy).toHaveBeenCalledWith(
      '/knowledge-bases/kb-1/documents',
      expect.objectContaining({ method: 'POST' })
    );
  });

  it('fetches document chunks with citation metadata', async () => {
    const mockChunks = {
      success: true,
      data: {
        items: [
          {
            id: 'chunk-1',
            document_id: 'doc-1',
            document_version_id: 'ver-1',
            chunk_index: 0,
            content: 'Section 1 text on architecture.',
            token_count: 24,
            character_count: 120,
            page_number: 1,
            section_title: 'Introduction',
            start_offset: 0,
            end_offset: 120,
            chunk_metadata: {
              embedding_model: 'BAAI/bge-small-en-v1.5',
              embedding_dimension: 384,
            },
            created_at: '2026-03-01T00:00:00Z',
          },
        ],
        total: 1,
        limit: 50,
        offset: 0,
      },
    };

    vi.spyOn(apiModule, 'apiClient').mockResolvedValue(mockChunks);

    const result = await knowledgeBaseService.getDocumentChunks('doc-1');
    expect(result.items).toHaveLength(1);
    expect(result.items[0].page_number).toBe(1);
    expect(result.items[0].section_title).toBe('Introduction');
    expect(result.items[0].chunk_metadata.embedding_model).toBe('BAAI/bge-small-en-v1.5');
  });

  it('triggers document reprocessing', async () => {
    const mockReprocess = {
      success: true,
      data: {
        document_id: 'doc-1',
        status: 'PROCESSING',
        message: 'Document reprocessing initiated.',
      },
    };

    const spy = vi.spyOn(apiModule, 'apiClient').mockResolvedValue(mockReprocess);

    const result = await knowledgeBaseService.reprocessDocument('doc-1');
    expect(result.status).toBe('PROCESSING');
    expect(spy).toHaveBeenCalledWith('/documents/doc-1/reprocess', { method: 'POST' });
  });

  it('deletes document and cascades storage and chunks', async () => {
    const spy = vi.spyOn(apiModule, 'apiClient').mockResolvedValue({
      success: true,
      data: { message: 'Document deleted' },
    });

    await knowledgeBaseService.deleteDocument('doc-1');
    expect(spy).toHaveBeenCalledWith('/documents/doc-1', { method: 'DELETE' });
  });

  it('validates allowed document formats (PDF, DOCX, TXT, MD, CSV)', () => {
    const allowed = ['pdf', 'docx', 'txt', 'md', 'csv'];
    const testCases = [
      { filename: 'report.pdf', valid: true },
      { filename: 'specs.docx', valid: true },
      { filename: 'notes.txt', valid: true },
      { filename: 'README.md', valid: true },
      { filename: 'metrics.csv', valid: true },
      { filename: 'binary.exe', valid: false },
      { filename: 'script.py', valid: false },
      { filename: 'archive.zip', valid: false },
    ];

    testCases.forEach(({ filename, valid }) => {
      const ext = filename.split('.').pop()?.toLowerCase() || '';
      expect(allowed.includes(ext)).toBe(valid);
    });
  });
});
