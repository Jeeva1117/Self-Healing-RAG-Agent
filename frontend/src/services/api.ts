import { config } from '@/config/env';
import type { ApiResponseEnvelope, AuthTokens } from '@/types/auth';

export class ApiError extends Error {
  code: string;
  status: number;
  details?: unknown;

  constructor(message: string, code: string, status: number, details?: unknown) {
    super(message);
    this.name = 'ApiError';
    this.code = code;
    this.status = status;
    this.details = details;
  }
}

export interface ApiClientOptions extends RequestInit {
  timeoutMs?: number;
}

// In-memory access token storage (short-lived, not kept in insecure localStorage)
let accessToken: string | null = null;
let refreshPromise: Promise<AuthTokens | null> | null = null;

export function setAccessToken(token: string | null) {
  accessToken = token;
}

export function getAccessToken(): string | null {
  return accessToken;
}

// Global listener for session expiration / auth failure
type AuthStateListener = (isAuthenticated: boolean) => void;
const authListeners: Set<AuthStateListener> = new Set();

export function onAuthStateChange(listener: AuthStateListener) {
  authListeners.add(listener);
  return () => {
    authListeners.delete(listener);
  };
}

function notifyAuthChange(isAuthenticated: boolean) {
  authListeners.forEach((listener) => listener(isAuthenticated));
}

/**
 * Shared, deduplicated refresh token executor.
 * Both silent 401 interceptor retries and explicit authService.refreshToken() calls
 * share this exact promise. This prevents concurrent React StrictMode or multiple component
 * refresh calls from sending duplicate requests to /auth/refresh, which would trigger
 * backend token reuse detection.
 */
export async function executeTokenRefresh(options?: {
  signal?: AbortSignal;
  timeoutMs?: number;
}): Promise<AuthTokens | null> {
  // If caller signal is already aborted, reject immediately without waiting
  if (options?.signal?.aborted) {
    throw new ApiError('Request was aborted', 'ABORTED', 0);
  }

  const timeoutMs = options?.timeoutMs ?? 8000;

  if (!refreshPromise) {
    refreshPromise = (async () => {
      // The underlying network request uses its own timeout controller,
      // completely isolated from individual caller unmounts (e.g. React StrictMode)
      const timeoutController = new AbortController();
      let didTimeout = false;

      const timeoutId = setTimeout(() => {
        didTimeout = true;
        timeoutController.abort();
      }, timeoutMs);

      try {
        const url = `${config.apiBaseUrl}/auth/refresh`;
        const response = await fetch(url, {
          method: 'POST',
          credentials: 'include',
          signal: timeoutController.signal,
          headers: {
            'Content-Type': 'application/json',
            'X-Request-ID': `client-refresh-${crypto.randomUUID()}`,
          },
        });

        if (!response.ok) {
          // Clear access token if unauthorized or session expired
          if (response.status === 401) {
            setAccessToken(null);
            notifyAuthChange(false);
            return null;
          }

          let errBody: ApiResponseEnvelope<unknown> | null = null;
          try {
            errBody = await response.json();
          } catch {
            // ignore
          }
          const message = errBody?.error?.message || `Token refresh failed with status ${response.status}`;
          const code = errBody?.error?.code || 'REFRESH_FAILED';
          throw new ApiError(message, code, response.status);
        }

        const json: ApiResponseEnvelope<AuthTokens> = await response.json();
        const tokens = json.data;
        if (tokens?.access_token) {
          setAccessToken(tokens.access_token);
          notifyAuthChange(true);
        }
        return tokens;
      } catch (err: unknown) {
        if (didTimeout) {
          throw new ApiError(
            'Authentication request timed out. Please check your connection and retry.',
            'TIMEOUT_ERROR',
            408
          );
        }
        if (err instanceof ApiError) {
          throw err;
        }
        throw new ApiError(
          err instanceof Error ? err.message : 'Network request failed',
          'NETWORK_ERROR',
          0
        );
      } finally {
        clearTimeout(timeoutId);
        refreshPromise = null;
      }
    })();
  }

  const activePromise = refreshPromise;

  // If caller provided an AbortSignal, wrap activePromise so ONLY this caller
  // rejects if its signal aborts, leaving activePromise running for other callers.
  if (options?.signal) {
    const signal = options.signal;
    return new Promise<AuthTokens | null>((resolve, reject) => {
      if (signal.aborted) {
        reject(new ApiError('Request was aborted', 'ABORTED', 0));
        return;
      }

      const onAbort = () => {
        reject(new ApiError('Request was aborted', 'ABORTED', 0));
      };

      signal.addEventListener('abort', onAbort, { once: true });

      activePromise
        .then((res) => {
          signal.removeEventListener('abort', onAbort);
          resolve(res);
        })
        .catch((err) => {
          signal.removeEventListener('abort', onAbort);
          reject(err);
        });
    });
  }

  return activePromise;
}

export async function apiClient<T>(
  endpoint: string,
  options: ApiClientOptions = {}
): Promise<T> {
  const url = `${config.apiBaseUrl}${endpoint}`;
  const headers = new Headers(options.headers || {});

  if (!headers.has('Content-Type') && !(options.body instanceof FormData)) {
    headers.set('Content-Type', 'application/json');
  }

  // Correlation ID tracing from browser client
  if (!headers.has('X-Request-ID')) {
    headers.set('X-Request-ID', `client-${crypto.randomUUID()}`);
  }

  // Attach access token if present and not already specified
  if (accessToken && !headers.has('Authorization')) {
    headers.set('Authorization', `Bearer ${accessToken}`);
  }

  const timeoutMs = options.timeoutMs ?? 10000;
  const controller = new AbortController();
  let didTimeout = false;

  const timeoutId = setTimeout(() => {
    didTimeout = true;
    controller.abort();
  }, timeoutMs);

  let callerAbortHandler: (() => void) | null = null;
  if (options.signal) {
    if (options.signal.aborted) {
      clearTimeout(timeoutId);
      throw new ApiError('Request was aborted', 'ABORTED', 0);
    }
    callerAbortHandler = () => controller.abort();
    options.signal.addEventListener('abort', callerAbortHandler);
  }

  let response: Response;
  try {
    response = await fetch(url, {
      ...options,
      signal: controller.signal,
      credentials: 'include',
      headers,
    });
  } catch (networkError: unknown) {
    if (didTimeout) {
      throw new ApiError(
        'Request timed out. Please check your connection and try again.',
        'TIMEOUT_ERROR',
        408
      );
    }
    if (options.signal?.aborted) {
      throw new ApiError('Request was aborted', 'ABORTED', 0);
    }
    throw new ApiError(
      networkError instanceof Error ? networkError.message : 'Network request failed',
      'NETWORK_ERROR',
      0
    );
  } finally {
    clearTimeout(timeoutId);
    if (options.signal && callerAbortHandler) {
      options.signal.removeEventListener('abort', callerAbortHandler);
    }
  }

  // 401 Interception: Attempt silent refresh once if not an auth endpoint
  const isAuthEndpoint =
    endpoint.startsWith('/auth/login') ||
    endpoint.startsWith('/auth/register') ||
    endpoint.startsWith('/auth/refresh') ||
    endpoint.startsWith('/auth/forgot-password') ||
    endpoint.startsWith('/auth/demo-login');

  if (response.status === 401 && !isAuthEndpoint) {
    try {
      const refreshed = await executeTokenRefresh({ timeoutMs: 8000 });
      if (refreshed?.access_token) {
        headers.set('Authorization', `Bearer ${refreshed.access_token}`);
        // Retry original request once
        const retryController = new AbortController();
        const retryTimeoutId = setTimeout(() => retryController.abort(), timeoutMs);
        try {
          response = await fetch(url, {
            ...options,
            signal: retryController.signal,
            credentials: 'include',
            headers,
          });
        } finally {
          clearTimeout(retryTimeoutId);
        }
      }
    } catch {
      // If refresh fails, fall through to error handling
    }
  }

  if (!response.ok) {
    let errorJson: ApiResponseEnvelope<unknown> | null = null;
    try {
      errorJson = await response.json();
    } catch {
      errorJson = null;
    }

    const message = errorJson?.error?.message || `Request failed with status ${response.status}`;
    const code = errorJson?.error?.code || 'HTTP_ERROR';
    throw new ApiError(message, code, response.status, errorJson?.error?.details);
  }

  return response.json();
}
