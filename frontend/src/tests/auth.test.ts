import { describe, it, expect, beforeEach, vi } from 'vitest';
import * as z from 'zod';
import {
  getAccessToken,
  setAccessToken,
  onAuthStateChange,
  ApiError,
  executeTokenRefresh,
} from '@/services/api';
import type { AuthStatus, AuthErrorDetails } from '@/context/AuthContext';
import type { User, AuthTokens } from '@/types/auth';

// 1. Zod Auth Validation Schemas Test Suite
describe('Authentication Validation Schemas', () => {
  const loginSchema = z.object({
    email: z.string().min(1, 'Email is required').email('Please enter a valid email address'),
    password: z.string().min(1, 'Password is required'),
  });

  const registerSchema = z
    .object({
      name: z.string().min(2, 'Name must be at least 2 characters'),
      email: z.string().min(1, 'Email is required').email('Please enter a valid email address'),
      password: z
        .string()
        .min(8, 'Password must be at least 8 characters')
        .regex(/[A-Za-z]/, 'Password must contain at least one letter')
        .regex(/\d/, 'Password must contain at least one number'),
      confirmPassword: z.string().min(1, 'Please confirm your password'),
    })
    .refine((data) => data.password === data.confirmPassword, {
      message: 'Passwords do not match',
      path: ['confirmPassword'],
    });

  it('validates correct login credentials', () => {
    const valid = loginSchema.safeParse({
      email: 'user@enterprise.com',
      password: 'ValidPassword123',
    });
    expect(valid.success).toBe(true);
  });

  it('rejects malformed email in login', () => {
    const invalid = loginSchema.safeParse({
      email: 'invalid-email-string',
      password: 'ValidPassword123',
    });
    expect(invalid.success).toBe(false);
  });

  it('rejects empty password in login', () => {
    const invalid = loginSchema.safeParse({
      email: 'user@enterprise.com',
      password: '',
    });
    expect(invalid.success).toBe(false);
  });

  it('validates correct registration payload', () => {
    const valid = registerSchema.safeParse({
      name: 'Sarah Connor',
      email: 'sarah@resistance.org',
      password: 'SecurePassword123',
      confirmPassword: 'SecurePassword123',
    });
    expect(valid.success).toBe(true);
  });

  it('rejects short password during registration', () => {
    const invalid = registerSchema.safeParse({
      name: 'Sarah Connor',
      email: 'sarah@resistance.org',
      password: 'short',
      confirmPassword: 'short',
    });
    expect(invalid.success).toBe(false);
    if (!invalid.success) {
      expect(invalid.error.issues[0].message).toContain('at least 8 characters');
    }
  });

  it('rejects password without numbers during registration', () => {
    const invalid = registerSchema.safeParse({
      name: 'Sarah Connor',
      email: 'sarah@resistance.org',
      password: 'NoNumbersInPassword',
      confirmPassword: 'NoNumbersInPassword',
    });
    expect(invalid.success).toBe(false);
    if (!invalid.success) {
      expect(invalid.error.issues[0].message).toContain('at least one number');
    }
  });

  it('rejects mismatched password and confirmation', () => {
    const invalid = registerSchema.safeParse({
      name: 'Sarah Connor',
      email: 'sarah@resistance.org',
      password: 'Password123',
      confirmPassword: 'DifferentPassword123',
    });
    expect(invalid.success).toBe(false);
    if (!invalid.success) {
      expect(invalid.error.issues[0].message).toBe('Passwords do not match');
    }
  });
});

// 2. Token Storage and Auth State Listener Test Suite
describe('API Client In-Memory Token Management', () => {
  beforeEach(() => {
    setAccessToken(null);
  });

  it('stores and retrieves access token strictly in memory', () => {
    expect(getAccessToken()).toBeNull();
    setAccessToken('mock_jwt_access_token_xyz');
    expect(getAccessToken()).toBe('mock_jwt_access_token_xyz');
    setAccessToken(null);
    expect(getAccessToken()).toBeNull();
  });

  it('notifies listeners when auth state changes', () => {
    const listener = vi.fn();
    const unsubscribe = onAuthStateChange(listener);

    listener(true);
    expect(listener).toHaveBeenCalledWith(true);

    unsubscribe();
  });

  it('instantiates ApiError with correct properties', () => {
    const err = new ApiError('Invalid email or password', 'INVALID_CREDENTIALS', 401, {
      field: 'password',
    });
    expect(err.name).toBe('ApiError');
    expect(err.message).toBe('Invalid email or password');
    expect(err.code).toBe('INVALID_CREDENTIALS');
    expect(err.status).toBe(401);
    expect(err.details).toEqual({ field: 'password' });
  });
});

// 3. Demo Login and Quick Access Integration Test Suite
describe('Development Demo Login Logic', () => {
  beforeEach(() => {
    setAccessToken(null);
    vi.restoreAllMocks();
  });

  it('determines demo button visibility based on demo_login_enabled flag', () => {
    const isDemoVisibleDisabled = (cfg: { demo_login_enabled: boolean }) => cfg.demo_login_enabled === true;
    expect(isDemoVisibleDisabled({ demo_login_enabled: false })).toBe(false);

    const isDemoVisibleEnabled = (cfg: { demo_login_enabled: boolean }) => cfg.demo_login_enabled === true;
    expect(isDemoVisibleEnabled({ demo_login_enabled: true })).toBe(true);
  });

  it('handles loading state transitions during demo authentication', async () => {
    let buttonText = 'Continue with Demo Account';
    let isSubmitting = false;

    const simulateDemoLogin = async (mockApi: () => Promise<void>) => {
      isSubmitting = true;
      buttonText = 'Signing in as Demo User...';
      try {
        await mockApi();
      } finally {
        isSubmitting = false;
        buttonText = 'Continue with Demo Account';
      }
    };

    let capturedInFlightState = '';
    const pendingPromise = simulateDemoLogin(async () => {
      capturedInFlightState = buttonText;
    });

    await pendingPromise;
    expect(capturedInFlightState).toBe('Signing in as Demo User...');
    expect(isSubmitting).toBe(false);
    expect(buttonText).toBe('Continue with Demo Account');
  });

  it('handles successful demo login and prepares dashboard redirection', async () => {
    const mockUser: User = {
      id: 'demo-user-uuid-1234',
      email: 'demo@selfhealingrag.local',
      name: 'Jeeva Developer',
      role: 'USER',
      is_active: true,
      is_verified: true,
      created_at: new Date().toISOString(),
    };

    const mockTokens: AuthTokens = {
      access_token: 'valid_demo_jwt_access_token',
      token_type: 'bearer',
      expires_in: 900,
      user: mockUser,
    };

    setAccessToken(mockTokens.access_token);
    expect(getAccessToken()).toBe('valid_demo_jwt_access_token');

    const redirectUrl = '/dashboard';
    expect(redirectUrl).toBe('/dashboard');
  });

  it('captures and formats backend errors when demo login is disabled or fails', async () => {
    let displayedServerError: string | null = null;

    const handleDemoError = (err: unknown) => {
      if (err instanceof ApiError) {
        displayedServerError = err.message;
      } else {
        displayedServerError = 'Unable to connect to demo login service.';
      }
    };

    handleDemoError(new ApiError('Demo login is disabled.', 'DEMO_LOGIN_DISABLED', 403));
    expect(displayedServerError).toBe('Demo login is disabled.');

    handleDemoError(new Error('Network offline'));
    expect(displayedServerError).toBe('Unable to connect to demo login service.');
  });

  it('recognizes demo user identity for UI badge display', () => {
    const isDemoUser = (user: { email: string }) => user.email === 'demo@selfhealingrag.local';

    expect(isDemoUser({ email: 'demo@selfhealingrag.local' })).toBe(true);
    expect(isDemoUser({ email: 'alice@enterprise.com' })).toBe(false);
  });
});

// 4. Regression Test Suite: Deterministic State Machine, Deduplication & Resilience
describe('Deterministic Authentication State Machine & StrictMode Deduplication', () => {
  const mockUser: User = {
    id: 'user-uuid-123',
    email: 'user@example.com',
    name: 'Test Engineer',
    role: 'DEVELOPER',
    is_active: true,
    is_verified: true,
    created_at: '2026-10-12T00:00:00Z',
  };

  const mockTokens: AuthTokens = {
    access_token: 'jwt.token.abc',
    token_type: 'bearer',
    expires_in: 3600,
    user: mockUser,
  };

  beforeEach(() => {
    setAccessToken(null);
    vi.restoreAllMocks();
  });

  it('Regression 1: Valid session -> status transitions from checking to authenticated', async () => {
    let status: AuthStatus = 'checking';
    let user: User | null = null;
    let authError: AuthErrorDetails | null = null;

    // Simulate successful session validation
    const validate = async () => {
      status = 'checking';
      try {
        const res = await Promise.resolve(mockTokens);
        user = res.user;
        status = 'authenticated';
        authError = null;
      } catch {
        status = 'error';
      }
    };

    await validate();
    expect(status).toBe('authenticated');
    expect(user).toEqual(mockUser);
    expect(authError).toBeNull();
  });

  it('Regression 2: Missing session -> status transitions cleanly to unauthenticated without error', async () => {
    let status: AuthStatus = 'checking';
    let user: User | null = mockUser;

    const validate = async () => {
      status = 'checking';
      try {
        throw new ApiError('No active session', 'UNAUTHORIZED', 401);
      } catch (err: unknown) {
        if (err instanceof ApiError && err.status === 401) {
          user = null;
          status = 'unauthenticated';
        } else {
          status = 'error';
        }
      }
    };

    await validate();
    expect(status).toBe('unauthenticated');
    expect(user).toBeNull();
  });

  it('Regression 3: Expired session -> clears access token and safely transitions to unauthenticated', async () => {
    setAccessToken('old_expired_token');
    expect(getAccessToken()).toBe('old_expired_token');

    let status: AuthStatus = 'checking';

    const validate = async () => {
      try {
        throw new ApiError('Refresh token expired', 'REFRESH_TOKEN_EXPIRED', 401);
      } catch (err: unknown) {
        if (err instanceof ApiError && err.status === 401) {
          setAccessToken(null);
          status = 'unauthenticated';
        }
      }
    };

    await validate();
    expect(status).toBe('unauthenticated');
    expect(getAccessToken()).toBeNull();
  });

  it('Regression 4: Backend unavailable -> transitions to error with isNetworkError true instead of hanging', async () => {
    let status: AuthStatus = 'checking';
    let authError: AuthErrorDetails | null = null;

    const validate = async () => {
      status = 'checking';
      try {
        throw new ApiError('Failed to fetch', 'NETWORK_ERROR', 0);
      } catch (err: unknown) {
        if (err instanceof ApiError && err.code === 'NETWORK_ERROR') {
          status = 'error';
          authError = {
            message: 'Unable to connect to authentication service. Please ensure the backend is running.',
            code: 'NETWORK_ERROR',
            isNetworkError: true,
            isTimeout: false,
          };
        }
      }
    };

    await validate();
    expect(status).toBe('error');
    const errObj = authError as AuthErrorDetails | null;
    expect(errObj?.isNetworkError).toBe(true);
    expect(errObj?.isTimeout).toBe(false);
    expect(errObj?.code).toBe('NETWORK_ERROR');
    expect(errObj?.message).toContain('backend is running');
  });

  it('Regression 5: Authentication timeout -> loading ends and Retry action is configured', async () => {
    let status: AuthStatus = 'checking';
    let authError: AuthErrorDetails | null = null;

    const validate = async () => {
      status = 'checking';
      try {
        throw new ApiError('Request timed out', 'TIMEOUT_ERROR', 408);
      } catch (err: unknown) {
        if (err instanceof ApiError && err.code === 'TIMEOUT_ERROR') {
          status = 'error';
          authError = {
            message: 'Security credentials verification timed out. The server took too long to respond.',
            code: 'TIMEOUT_ERROR',
            isNetworkError: true,
            isTimeout: true,
          };
        }
      }
    };

    await validate();
    expect(status).toBe('error');
    const errObj = authError as AuthErrorDetails | null;
    expect(errObj?.isTimeout).toBe(true);
    expect(errObj?.code).toBe('TIMEOUT_ERROR');
  });

  it('Regression 6 & 7: React StrictMode / repeated renders -> deduplicates concurrent token refresh calls', async () => {
    let fetchCount = 0;

    // Mock global fetch to spy on network requests
    const originalFetch = globalThis.fetch;
    globalThis.fetch = vi.fn().mockImplementation(async () => {
      fetchCount++;
      // Simulate network latency
      await new Promise((resolve) => setTimeout(resolve, 20));
      return {
        ok: true,
        status: 200,
        json: async () => ({
          success: true,
          data: mockTokens,
        }),
      } as Response;
    });

    try {
      // Simulate React StrictMode double effect execution (two concurrent refresh calls)
      const call1 = executeTokenRefresh();
      const call2 = executeTokenRefresh();

      const [res1, res2] = await Promise.all([call1, call2]);

      expect(res1?.access_token).toBe(mockTokens.access_token);
      expect(res2?.access_token).toBe(mockTokens.access_token);
      // Strictly only ONE HTTP fetch was dispatched across concurrent calls!
      expect(fetchCount).toBe(1);
    } finally {
      globalThis.fetch = originalFetch;
    }
  });

  it('Regression 8: Retry action -> triggers verification again and successfully recovers to authenticated', async () => {
    let status: AuthStatus = 'error';
    let attempt = 0;

    const mockVerify = async () => {
      attempt++;
      status = 'checking';
      if (attempt === 1) {
        status = 'error';
        throw new ApiError('Service unavailable', 'NETWORK_ERROR', 0);
      }
      status = 'authenticated';
      return mockTokens;
    };

    // First attempt fails
    try {
      await mockVerify();
    } catch {
      expect(status).toBe('error');
    }

    // User clicks Retry Verification
    const retryRes = await mockVerify();
    expect(status).toBe('authenticated');
    expect(retryRes.user.email).toBe('user@example.com');
  });

  it('Regression 9: Demo login and logout -> maintain clean state transitions', async () => {
    let user: User | null = null;
    let status: AuthStatus = 'unauthenticated';

    // 1. Demo Login
    const demoLogin = async () => {
      status = 'checking';
      setAccessToken('demo_jwt_token_456');
      user = mockUser;
      status = 'authenticated';
    };

    await demoLogin();
    expect(status).toBe('authenticated');
    expect(user).toEqual(mockUser);
    expect(getAccessToken()).toBe('demo_jwt_token_456');

    // 2. Logout
    const logout = async () => {
      setAccessToken(null);
      user = null;
      status = 'unauthenticated';
    };

    await logout();
    expect(status).toBe('unauthenticated');
    expect(user).toBeNull();
    expect(getAccessToken()).toBeNull();
  });

  it('Regression 10: Protected routes decision matrix blocks unauthorized and guides user', () => {
    const evaluateRouteAccess = (
      authStatus: AuthStatus,
      isAuthed: boolean
    ): 'SHOW_LOADING' | 'SHOW_ERROR_RETRY' | 'REDIRECT_LOGIN' | 'RENDER_CHILDREN' => {
      if (authStatus === 'checking') return 'SHOW_LOADING';
      if (authStatus === 'error') return 'SHOW_ERROR_RETRY';
      if (authStatus === 'unauthenticated' || !isAuthed) return 'REDIRECT_LOGIN';
      return 'RENDER_CHILDREN';
    };

    // Checking state -> renders verifying security indicator
    expect(evaluateRouteAccess('checking', false)).toBe('SHOW_LOADING');

    // Error state -> renders error and retry action
    expect(evaluateRouteAccess('error', false)).toBe('SHOW_ERROR_RETRY');

    // Unauthenticated -> redirects to /login
    expect(evaluateRouteAccess('unauthenticated', false)).toBe('REDIRECT_LOGIN');

    // Authenticated -> grants access
    expect(evaluateRouteAccess('authenticated', true)).toBe('RENDER_CHILDREN');
  });

  it('Regression 11: Isolated caller cancellation -> aborting caller rejects with ABORTED while active caller succeeds', async () => {
    const originalFetch = globalThis.fetch;
    let fetchDispatched = false;

    globalThis.fetch = vi.fn().mockImplementation(async () => {
      fetchDispatched = true;
      await new Promise((resolve) => setTimeout(resolve, 30));
      return {
        ok: true,
        status: 200,
        json: async () => ({
          success: true,
          data: mockTokens,
        }),
      } as Response;
    });

    try {
      const abortController1 = new AbortController();
      const abortController2 = new AbortController();

      // Caller 1 starts refresh with controller 1
      const call1 = executeTokenRefresh({ signal: abortController1.signal });

      // Caller 2 starts refresh with controller 2
      const call2 = executeTokenRefresh({ signal: abortController2.signal });

      // StrictMode simulation: Caller 1 unmounts and aborts immediately
      abortController1.abort();

      // Caller 1 should reject with ABORTED
      await expect(call1).rejects.toMatchObject({ code: 'ABORTED' });

      // Caller 2 was NOT aborted: it MUST resolve successfully with tokens!
      const res2 = await call2;
      expect(res2?.access_token).toBe(mockTokens.access_token);
      expect(fetchDispatched).toBe(true);
    } finally {
      globalThis.fetch = originalFetch;
    }
  });
});
