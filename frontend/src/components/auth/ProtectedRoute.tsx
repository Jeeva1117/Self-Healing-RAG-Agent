import React, { useState } from 'react';
import { Navigate, useLocation, Link } from 'react-router-dom';
import { useAuth } from '@/context/AuthContext';
import { ShieldCheck, AlertTriangle, WifiOff, RefreshCw, LogIn } from 'lucide-react';
import { Button } from '@/components/ui/button';

interface ProtectedRouteProps {
  children?: React.ReactNode;
}

export function ProtectedRoute({ children }: ProtectedRouteProps) {
  const { status, isAuthenticated, authError, retryAuth } = useAuth();
  const location = useLocation();
  const [isRetrying, setIsRetrying] = useState(false);

  const handleRetry = async () => {
    setIsRetrying(true);
    try {
      await retryAuth();
    } finally {
      setIsRetrying(false);
    }
  };

  // State: checking -> Display accessible credential verification indicator
  if (status === 'checking') {
    return (
      <div
        role="status"
        aria-live="polite"
        className="flex min-h-screen w-full flex-col items-center justify-center bg-slate-50 dark:bg-[#070A12] text-slate-800 dark:text-slate-200 p-4"
      >
        <div className="flex flex-col items-center gap-4 animate-in fade-in-50 duration-300 max-w-sm text-center">
          <div className="relative flex h-14 w-14 items-center justify-center rounded-2xl bg-blue-600/10 border border-blue-500/20 text-blue-600 dark:text-blue-400">
            <ShieldCheck className="h-7 w-7 animate-pulse" />
            <div className="absolute inset-0 rounded-2xl ring-2 ring-blue-500/30 animate-ping opacity-25" />
          </div>
          <div className="space-y-1">
            <h3 className="text-sm font-semibold tracking-tight text-slate-900 dark:text-slate-100">
              Verifying Security Credentials
            </h3>
            <p className="text-xs text-slate-500 dark:text-slate-400">
              Validating session and access privileges...
            </p>
          </div>
          <div className="w-48 h-1 bg-slate-200 dark:bg-slate-800 rounded-full overflow-hidden mt-1">
            <div className="h-full w-2/3 bg-blue-600 dark:bg-blue-500 rounded-full animate-pulse" />
          </div>
        </div>
      </div>
    );
  }

  // State: error -> Display clear error and retry action
  if (status === 'error') {
    const isTimeout = authError?.isTimeout;
    const redirectParam = encodeURIComponent(location.pathname + location.search);

    return (
      <div
        role="alert"
        className="flex min-h-screen w-full flex-col items-center justify-center bg-slate-50 dark:bg-[#070A12] text-slate-800 dark:text-slate-200 p-4"
      >
        <div className="w-full max-w-md rounded-2xl border border-slate-200 bg-white p-6 sm:p-8 shadow-xl dark:border-slate-800 dark:bg-[#0B0F19] text-center space-y-5 animate-in fade-in-50 duration-200">
          <div className="mx-auto flex h-14 w-14 items-center justify-center rounded-2xl bg-rose-500/10 border border-rose-500/20 text-rose-600 dark:text-rose-400">
            {isTimeout ? (
              <AlertTriangle className="h-7 w-7" />
            ) : (
              <WifiOff className="h-7 w-7" />
            )}
          </div>

          <div className="space-y-2">
            <h3 className="text-base font-semibold tracking-tight text-slate-900 dark:text-slate-100">
              {isTimeout ? 'Verification Timed Out' : 'Service Connection Error'}
            </h3>
            <p className="text-xs text-slate-600 dark:text-slate-400 leading-relaxed">
              {authError?.message ||
                'Unable to verify your session credentials due to a service connectivity issue.'}
            </p>
            <p className="text-[11px] text-slate-400 dark:text-slate-500 font-mono">
              Status Code: {authError?.code || 'AUTH_CHECK_FAILED'}
            </p>
          </div>

          <div className="flex flex-col sm:flex-row items-center justify-center gap-3 pt-2">
            <Button
              id="retry-auth-button"
              type="button"
              onClick={handleRetry}
              disabled={isRetrying}
              className="w-full sm:w-auto inline-flex items-center justify-center gap-2 px-4 py-2 text-xs font-semibold rounded-xl bg-blue-600 text-white hover:bg-blue-700 transition cursor-pointer"
            >
              <RefreshCw className={`h-3.5 w-3.5 ${isRetrying ? 'animate-spin' : ''}`} />
              <span>{isRetrying ? 'Retrying...' : 'Retry Verification'}</span>
            </Button>

            <Link
              id="auth-go-to-login"
              to={`/login?redirect=${redirectParam}`}
              className="w-full sm:w-auto inline-flex items-center justify-center gap-1.5 px-4 py-2 text-xs font-medium rounded-xl border border-slate-200 text-slate-700 hover:bg-slate-50 dark:border-slate-800 dark:text-slate-300 dark:hover:bg-slate-900 transition"
            >
              <LogIn className="h-3.5 w-3.5" />
              <span>Go to Sign In</span>
            </Link>
          </div>
        </div>
      </div>
    );
  }

  // State: unauthenticated -> Navigate cleanly to login page
  if (status === 'unauthenticated' || !isAuthenticated) {
    const redirectParam = encodeURIComponent(location.pathname + location.search);
    return <Navigate to={`/login?redirect=${redirectParam}`} replace />;
  }

  // State: authenticated -> Render protected content
  return <>{children}</>;
}
