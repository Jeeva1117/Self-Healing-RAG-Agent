import { Link } from 'react-router-dom';
import { ArrowLeft, ShieldAlert, Sparkles } from 'lucide-react';
import { Button } from '@/components/ui/button';

export function ResetPasswordPage() {
  return (
    <div className="min-h-screen w-full flex items-center justify-center p-4 sm:p-6 bg-slate-50 dark:bg-[#070A12] text-slate-900 dark:text-slate-100 transition-colors">
      <div className="w-full max-w-md space-y-6">
        <div className="text-center space-y-2">
          <div className="inline-flex items-center gap-2 px-3 py-1.5 rounded-full bg-blue-50 border border-blue-200/80 text-blue-700 dark:bg-blue-950/40 dark:border-blue-900/50 dark:text-blue-400 text-xs font-semibold shadow-2xs">
            <Sparkles className="h-3.5 w-3.5" />
            <span>Security Flow</span>
          </div>
          <h1 className="text-2xl sm:text-3xl font-bold tracking-tight text-slate-900 dark:text-slate-100">
            Password Reset
          </h1>
          <p className="text-xs sm:text-sm text-slate-500 dark:text-slate-400">
            Password reset token verification
          </p>
        </div>

        <div className="rounded-2xl border border-slate-200/90 bg-white p-6 sm:p-8 shadow-xl shadow-slate-200/50 dark:border-slate-800/80 dark:bg-[#0B0F19] dark:shadow-2xl dark:shadow-black/50 text-center space-y-4">
          <div className="mx-auto flex h-12 w-12 items-center justify-center rounded-2xl bg-amber-500/10 text-amber-600 dark:text-amber-400 border border-amber-500/20">
            <ShieldAlert className="h-6 w-6" />
          </div>

          <div className="space-y-1">
            <h3 className="text-sm font-semibold text-slate-900 dark:text-slate-100">
              Email Dispatcher Not Configured
            </h3>
            <p className="text-xs text-slate-500 dark:text-slate-400 leading-relaxed">
              Automated password reset tokens require an outbound SMTP service. To reset your credentials in this environment, please ask an administrator to update your account, or sign in if you know your credentials.
            </p>
          </div>

          <div className="pt-3">
            <Link to="/login">
              <Button className="w-full gap-2">
                <ArrowLeft className="h-4 w-4" />
                <span>Return to Sign In</span>
              </Button>
            </Link>
          </div>
        </div>
      </div>
    </div>
  );
}
