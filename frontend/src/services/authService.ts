import { apiClient, setAccessToken, executeTokenRefresh, ApiError } from '@/services/api';
import type { ApiResponseEnvelope, AuthTokens, SessionInfo, User } from '@/types/auth';

export const authService = {
  async login(payload: { email: string; password: string }): Promise<AuthTokens> {
    const res = await apiClient<ApiResponseEnvelope<AuthTokens>>('/auth/login', {
      method: 'POST',
      body: JSON.stringify(payload),
    });
    setAccessToken(res.data.access_token);
    return res.data;
  },

  async register(payload: { email: string; password: string; name: string }): Promise<User> {
    const res = await apiClient<ApiResponseEnvelope<User>>('/auth/register', {
      method: 'POST',
      body: JSON.stringify(payload),
    });
    return res.data;
  },

  async getMe(): Promise<User> {
    const res = await apiClient<ApiResponseEnvelope<User>>('/auth/me');
    return res.data;
  },

  async refreshToken(options?: { signal?: AbortSignal; timeoutMs?: number }): Promise<AuthTokens> {
    const tokens = await executeTokenRefresh(options);
    if (!tokens) {
      throw new ApiError('No active session or session has expired.', 'UNAUTHORIZED', 401);
    }
    return tokens;
  },

  async logout(): Promise<void> {
    try {
      await apiClient<ApiResponseEnvelope<{ message: string }>>('/auth/logout', {
        method: 'POST',
      });
    } finally {
      setAccessToken(null);
    }
  },

  async logoutAll(): Promise<void> {
    try {
      await apiClient<ApiResponseEnvelope<{ message: string }>>('/auth/logout-all', {
        method: 'POST',
      });
    } finally {
      setAccessToken(null);
    }
  },

  async changePassword(payload: { current_password: string; new_password: string }): Promise<string> {
    const res = await apiClient<ApiResponseEnvelope<{ message: string }>>('/auth/change-password', {
      method: 'POST',
      body: JSON.stringify(payload),
    });
    setAccessToken(null);
    return res.data.message;
  },

  async getSessions(): Promise<SessionInfo[]> {
    const res = await apiClient<ApiResponseEnvelope<SessionInfo[]>>('/auth/sessions');
    return res.data;
  },

  async revokeSession(sessionId: string): Promise<void> {
    await apiClient<ApiResponseEnvelope<{ message: string }>>(`/auth/sessions/${sessionId}`, {
      method: 'DELETE',
    });
  },

  async forgotPassword(email: string): Promise<{ status: string; message: string }> {
    const res = await apiClient<ApiResponseEnvelope<{ status: string; message: string; email: string }>>(
      '/auth/forgot-password',
      {
        method: 'POST',
        body: JSON.stringify({ email }),
      }
    );
    return res.data;
  },

  async getAuthConfig(): Promise<{ demo_login_enabled: boolean; environment?: string }> {
    const res = await apiClient<ApiResponseEnvelope<{ demo_login_enabled: boolean; environment?: string }>>(
      '/auth/config'
    );
    return res.data;
  },

  async demoLogin(): Promise<AuthTokens> {
    const res = await apiClient<ApiResponseEnvelope<AuthTokens>>('/auth/demo-login', {
      method: 'POST',
    });
    setAccessToken(res.data.access_token);
    return res.data;
  },
};
