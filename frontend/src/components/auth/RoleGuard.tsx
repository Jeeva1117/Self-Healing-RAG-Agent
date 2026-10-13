import React from 'react';
import { useAuth } from '@/context/AuthContext';
import type { UserRole } from '@/types/auth';
import { ShieldAlert } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { useNavigate } from 'react-router-dom';

interface RoleGuardProps {
  allowedRoles: UserRole[];
  children: React.ReactNode;
  fallback?: React.ReactNode;
}

export function RoleGuard({ allowedRoles, children, fallback }: RoleGuardProps) {
  const { user } = useAuth();
  const navigate = useNavigate();

  if (!user || !allowedRoles.includes(user.role)) {
    if (fallback) {
      return <>{fallback}</>;
    }

    return (
      <div className="rounded-2xl border border-rose-200/80 bg-rose-50/50 p-6 text-center dark:border-rose-900/40 dark:bg-rose-950/20 max-w-lg mx-auto my-8">
        <div className="mx-auto flex h-12 w-12 items-center justify-center rounded-xl bg-rose-100 text-rose-600 dark:bg-rose-900/40 dark:text-rose-400 mb-3">
          <ShieldAlert className="h-6 w-6" />
        </div>
        <h3 className="text-base font-semibold text-slate-900 dark:text-slate-100">
          Access Restricted
        </h3>
        <p className="mt-1 text-xs text-slate-600 dark:text-slate-400">
          This administrative feature requires one of the following roles:{' '}
          <span className="font-semibold">{allowedRoles.join(', ')}</span>. Your current role is{' '}
          <span className="font-semibold">{user?.role || 'None'}</span>.
        </p>
        <div className="mt-4 flex justify-center gap-3">
          <Button variant="outline" size="sm" onClick={() => navigate(-1)}>
            Go Back
          </Button>
          <Button size="sm" onClick={() => navigate('/chat')}>
            Return to Workspace
          </Button>
        </div>
      </div>
    );
  }

  return <>{children}</>;
}
