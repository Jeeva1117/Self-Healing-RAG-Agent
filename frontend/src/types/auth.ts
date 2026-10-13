export type UserRole = 'USER' | 'ADMIN' | 'DEVELOPER' | 'ANALYST' | 'OWNER';

export interface User {
  id: string;
  email: string;
  name: string;
  role: UserRole;
  is_active: boolean;
  is_verified: boolean;
  created_at: string;
  last_login_at?: string | null;
}

export interface AuthTokens {
  access_token: string;
  token_type: string;
  expires_in: number;
  user: User;
}

export interface SessionInfo {
  id: string;
  created_at: string;
  expires_at: string;
  last_used_at?: string | null;
  user_agent?: string | null;
  ip_address?: string | null;
  is_current: boolean;
}

export interface ApiResponseEnvelope<T> {
  success: boolean;
  data: T;
  error?: {
    code: string;
    message: string;
    details?: unknown;
  };
  meta?: {
    request_id?: string;
    timestamp: string;
  };
}
