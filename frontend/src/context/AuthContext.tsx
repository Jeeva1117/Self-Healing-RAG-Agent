import React, { createContext, useContext, useEffect, useState, useCallback, useRef } from 'react';
import { authService } from '@/services/authService';
import { onAuthStateChange, setAccessToken, ApiError } from '@/services/api';
import type { User } from '@/types/auth';

export type AuthStatus = 'checking' | 'authenticated' | 'unauthenticated' | 'error';

export interface AuthErrorDetails {
  message: string;
  code: string;
  isNetworkError: boolean;
  isTimeout: boolean;
}

export interface AuthContextType {
  user: User | null;
  status: AuthStatus;
  isLoading: boolean;
  isAuthenticated: boolean;
  authError: AuthErrorDetails | null;
  login: (credentials: { email: string; password: string }) => Promise<User>;
  demoLogin: () => Promise<User>;
  register: (payload: { email: string; password: string; name: string }) => Promise<User>;
  logout: () => Promise<void>;
  logoutAll: () => Promise<void>;
  refreshUser: () => Promise<void>;
  retryAuth: () => Promise<void>;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [status, setStatus] = useState<AuthStatus>('checking');
  const [authError, setAuthError] = useState<AuthErrorDetails | null>(null);

  // Active validation AbortController reference to cancel superseded requests
  const activeAbortRef = useRef<AbortController | null>(null);

  // Validate session with deterministic state machine transitions
  const validateSession = useCallback(async (signal?: AbortSignal) => {
    setStatus('checking');
    setAuthError(null);

    try {
      // Attempt silent refresh via HttpOnly cookie (deduplicated across calls)
      const tokens = await authService.refreshToken({ signal, timeoutMs: 8000 });
      if (signal?.aborted) return;
      setUser(tokens.user);
      setStatus('authenticated');
      setAuthError(null);
    } catch (err: unknown) {
      // ONLY skip state update if THIS caller's signal was aborted due to unmount
      if (signal?.aborted) {
        return;
      }

      if (err instanceof ApiError && err.status === 401) {
        // Missing, expired, or invalid session cookie: unauthenticated
        setAccessToken(null);
        setUser(null);
        setStatus('unauthenticated');
        setAuthError(null);
      } else if (err instanceof ApiError && err.code === 'TIMEOUT_ERROR') {
        // Server or database took longer than the configured timeout
        setStatus('error');
        setAuthError({
          message: 'Security credentials verification timed out. The server took too long to respond.',
          code: 'TIMEOUT_ERROR',
          isNetworkError: true,
          isTimeout: true,
        });
      } else if (err instanceof ApiError && err.code === 'NETWORK_ERROR') {
        // Backend service is unreachable or network is disconnected
        setStatus('error');
        setAuthError({
          message: 'Unable to connect to authentication service. Please ensure the backend is running.',
          code: 'NETWORK_ERROR',
          isNetworkError: true,
          isTimeout: false,
        });
      } else {
        // If an aborted error was received while mounted, treat as unauthenticated
        if (err instanceof ApiError && err.code === 'ABORTED') {
          setAccessToken(null);
          setUser(null);
          setStatus('unauthenticated');
          setAuthError(null);
          return;
        }

        // Recoverable or 5xx service failure
        setStatus('error');
        setAuthError({
          message: 'An unexpected service error occurred while verifying credentials.',
          code: err instanceof ApiError ? err.code : 'SERVICE_ERROR',
          isNetworkError: false,
          isTimeout: false,
        });
      }
    }
  }, []);

  // Initialize session on mount with React StrictMode / unmount resilience
  useEffect(() => {
    const controller = new AbortController();
    activeAbortRef.current = controller;

    validateSession(controller.signal);

    // Watchdog fallback: Guarantee verification never stays stuck on 'checking' indefinitely
    const watchdogId = setTimeout(() => {
      setStatus((currentStatus) => {
        if (currentStatus === 'checking') {
          setAuthError({
            message: 'Session verification took longer than expected. Please retry or sign in.',
            code: 'TIMEOUT_WATCHDOG',
            isNetworkError: true,
            isTimeout: true,
          });
          return 'error';
        }
        return currentStatus;
      });
    }, 9000);

    // Listen to global 401 expirations
    const unsubscribe = onAuthStateChange((isAuthed) => {
      if (!isAuthed) {
        setUser(null);
        setStatus('unauthenticated');
      }
    });

    return () => {
      clearTimeout(watchdogId);
      controller.abort();
      unsubscribe();
    };
  }, [validateSession]);

  const retryAuth = useCallback(async () => {
    if (activeAbortRef.current) {
      activeAbortRef.current.abort();
    }
    const controller = new AbortController();
    activeAbortRef.current = controller;
    await validateSession(controller.signal);
  }, [validateSession]);

  const login = async (credentials: { email: string; password: string }): Promise<User> => {
    setStatus('checking');
    try {
      const data = await authService.login(credentials);
      setUser(data.user);
      setStatus('authenticated');
      setAuthError(null);
      return data.user;
    } catch (err) {
      setStatus('unauthenticated');
      throw err;
    }
  };

  const demoLogin = async (): Promise<User> => {
    setStatus('checking');
    try {
      const data = await authService.demoLogin();
      setUser(data.user);
      setStatus('authenticated');
      setAuthError(null);
      return data.user;
    } catch (err) {
      setStatus('unauthenticated');
      throw err;
    }
  };

  const register = async (payload: { email: string; password: string; name: string }): Promise<User> => {
    const newUser = await authService.register(payload);
    return newUser;
  };

  const logout = async (): Promise<void> => {
    try {
      await authService.logout();
    } finally {
      setUser(null);
      setStatus('unauthenticated');
      setAuthError(null);
    }
  };

  const logoutAll = async (): Promise<void> => {
    try {
      await authService.logoutAll();
    } finally {
      setUser(null);
      setStatus('unauthenticated');
      setAuthError(null);
    }
  };

  const refreshUser = async (): Promise<void> => {
    try {
      const freshUser = await authService.getMe();
      setUser(freshUser);
    } catch {
      setUser(null);
      setStatus('unauthenticated');
    }
  };

  const value: AuthContextType = {
    user,
    status,
    isLoading: status === 'checking',
    isAuthenticated: status === 'authenticated' && !!user,
    authError,
    login,
    demoLogin,
    register,
    logout,
    logoutAll,
    refreshUser,
    retryAuth,
  };

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthContextType {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
}
