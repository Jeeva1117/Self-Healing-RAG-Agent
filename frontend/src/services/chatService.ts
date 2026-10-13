import { apiClient } from './api';
import type { ChatResponseData, SendChatRequest } from '@/types/chat';

interface ApiResponse<T> {
  success: boolean;
  data: T;
  error?: {
    code: string;
    message: string;
    details?: unknown;
  };
}

export const chatService = {
  /**
   * Sends a grounded query to /api/v1/chat scoped to a knowledge base.
   */
  sendMessage: async (
    requestOrPrompt: SendChatRequest | string,
    legacyKbIdOrConversationId?: string
  ): Promise<ChatResponseData> => {
    let payload: SendChatRequest;

    if (typeof requestOrPrompt === 'string') {
      payload = {
        prompt: requestOrPrompt,
        knowledge_base_id: legacyKbOrConversationId(legacyKbIdOrConversationId),
      };
    } else {
      payload = requestOrPrompt;
    }

    const res = await apiClient<ApiResponse<ChatResponseData>>('/chat', {
      method: 'POST',
      body: JSON.stringify(payload),
    });

    return res.data;
  },
};

function legacyKbOrConversationId(id?: string): string {
  return id || '';
}
