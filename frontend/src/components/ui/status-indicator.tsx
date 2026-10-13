import { cn } from '@/lib/utils';

export type SystemStatusType = 'operational' | 'connected' | 'disconnected' | 'degraded' | 'not_configured' | 'coming_soon';

interface StatusIndicatorProps {
  status: SystemStatusType;
  label?: string;
  showDotOnly?: boolean;
}

export function StatusIndicator({ status, label, showDotOnly = false }: StatusIndicatorProps) {
  const configs: Record<SystemStatusType, { dot: string; text: string; defaultLabel: string }> = {
    operational: {
      dot: 'bg-emerald-400',
      text: 'text-emerald-400 light:text-emerald-600',
      defaultLabel: 'Operational',
    },
    connected: {
      dot: 'bg-emerald-400',
      text: 'text-emerald-400 light:text-emerald-600',
      defaultLabel: 'Connected',
    },
    degraded: {
      dot: 'bg-amber-400',
      text: 'text-amber-400 light:text-amber-600',
      defaultLabel: 'Degraded',
    },
    disconnected: {
      dot: 'bg-rose-400',
      text: 'text-rose-400 light:text-rose-600',
      defaultLabel: 'Disconnected',
    },
    not_configured: {
      dot: 'bg-slate-500',
      text: 'text-slate-400 light:text-slate-500',
      defaultLabel: 'Not configured',
    },
    coming_soon: {
      dot: 'bg-indigo-400',
      text: 'text-indigo-400 light:text-indigo-600',
      defaultLabel: 'Coming soon',
    },
  };

  const current = configs[status] || configs.not_configured;

  return (
    <div className="inline-flex items-center gap-2 select-none">
      <span className="relative flex h-2 w-2">
        {(status === 'operational' || status === 'connected') && (
          <span className={cn('animate-ping absolute inline-flex h-full w-full rounded-full opacity-75', current.dot)} />
        )}
        <span className={cn('relative inline-flex rounded-full h-2 w-2', current.dot)} />
      </span>
      {!showDotOnly && (
        <span className={cn('text-xs font-medium', current.text)}>
          {label || current.defaultLabel}
        </span>
      )}
    </div>
  );
}
