import { describe, it, expect, vi, beforeEach } from 'vitest';
import { chatService } from '@/services/chatService';
import * as apiModule from '@/services/api';

describe('Chat Service & Scoped Knowledge Base Validations', () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it('sends prompt with knowledge_base_id to /chat endpoint', async () => {
    const mockChatResponse = {
      success: true,
      data: {
        id: 'm-123',
        role: 'assistant',
        content: 'In Python, arithmetic operators include +, -, *, and / [1].',
        timestamp: '2026-10-09T12:00:00Z',
        knowledge_base_id: 'kb-python-uuid',
        citations: [
          {
            id: 1,
            chunk_id: 'chunk-1',
            document_id: 'doc-1',
            title: 'Python_Notes.pdf',
            section: '4. Operators',
            page: 3,
            snippet: 'Arithmetic operators include +, -, *, /',
            relevance_score: 0.95,
          },
        ],
        confidence: null,
        verification_status: 'grounded_evidence',
        is_insufficient_evidence: false,
        retrieval_latency: {
          vector_ms: 25.4,
          lexical_ms: 12.1,
          fusion_ms: 3.2,
          rerank_ms: 45.0,
          total_ms: 85.7,
        },
        generation_ms: 110.5,
        total_ms: 196.2,
        model: 'grounded-synthesis',
      },
    };

    const spy = vi.spyOn(apiModule, 'apiClient').mockResolvedValue(mockChatResponse);

    const result = await chatService.sendMessage({
      knowledge_base_id: 'kb-python-uuid',
      prompt: 'What are operators in Python?',
      top_k: 5,
    });

    expect(spy).toHaveBeenCalledWith('/chat', {
      method: 'POST',
      body: JSON.stringify({
        knowledge_base_id: 'kb-python-uuid',
        prompt: 'What are operators in Python?',
        top_k: 5,
      }),
    });

    expect(result.id).toBe('m-123');
    expect(result.content).toContain('arithmetic operators');
    expect(result.citations).toHaveLength(1);
    expect(result.citations[0].title).toBe('Python_Notes.pdf');
    expect(result.is_insufficient_evidence).toBe(false);
    expect(result.confidence).toBeNull();
  });

  it('handles insufficient evidence response correctly', async () => {
    const mockInsufficient = {
      success: true,
      data: {
        id: 'm-456',
        role: 'assistant',
        content: 'I could not find sufficient matching information in the selected knowledge base to answer your question.',
        timestamp: '2026-10-09T12:01:00Z',
        knowledge_base_id: 'kb-python-uuid',
        citations: [],
        confidence: null,
        verification_status: 'insufficient_evidence',
        is_insufficient_evidence: true,
        retrieval_latency: {
          vector_ms: 20.0,
          lexical_ms: 10.0,
          fusion_ms: 2.0,
          rerank_ms: 0.0,
          total_ms: 32.0,
        },
        generation_ms: 0.0,
        total_ms: 32.0,
        model: '',
      },
    };

    vi.spyOn(apiModule, 'apiClient').mockResolvedValue(mockInsufficient);

    const result = await chatService.sendMessage({
      knowledge_base_id: 'kb-python-uuid',
      prompt: 'What is the refund policy for enterprise?',
    });

    expect(result.is_insufficient_evidence).toBe(true);
    expect(result.citations).toHaveLength(0);
    expect(result.verification_status).toBe('insufficient_evidence');
  });

  it('handles general AI answer without document citations', async () => {
    const mockGeneralAIResponse = {
      success: true,
      data: {
        id: 'm-789',
        role: 'assistant',
        content: 'Recursion is a programming technique where a function calls itself.',
        timestamp: '2026-10-09T12:02:00Z',
        knowledge_base_id: 'kb-python-uuid',
        citations: [],
        confidence: null,
        verification_status: 'general_ai_answer',
        is_insufficient_evidence: false,
        answer_type: 'general_ai',
        generation_ms: 150.0,
        total_ms: 200.0,
        model: 'llama-3.3-70b-versatile',
      },
    };

    vi.spyOn(apiModule, 'apiClient').mockResolvedValue(mockGeneralAIResponse);

    const result = await chatService.sendMessage({
      knowledge_base_id: 'kb-python-uuid',
      prompt: 'Explain recursion in simple terms with a Python example',
    });

    expect(result.id).toBe('m-789');
    expect(result.answer_type).toBe('general_ai');
    expect(result.citations).toHaveLength(0);
    expect(result.is_insufficient_evidence).toBe(false);
    expect(result.model).toBe('llama-3.3-70b-versatile');
  });

  it('propagates API error when backend rejects unauthorized access', async () => {
    vi.spyOn(apiModule, 'apiClient').mockRejectedValue(
      new apiModule.ApiError('Knowledge base not found or access denied.', 'KNOWLEDGE_BASE_NOT_FOUND', 404)
    );

    await expect(
      chatService.sendMessage({
        knowledge_base_id: 'unauthorized-kb-id',
        prompt: 'Secret question',
      })
    ).rejects.toThrow('Knowledge base not found or access denied.');
  });
});
