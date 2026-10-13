import { Badge } from '@/components/ui/badge';

interface StatusBadgeProps {
  status: 'healthy' | 'unhealthy' | 'degraded' | 'loading' | 'disabled';
  label?: string;
}

export function StatusBadge({ status, label }: StatusBadgeProps) {
  if (status === 'loading') {
    return (
      <Badge variant="outline" className="gap-1.5 py-1">
        <span className="h-2 w-2 rounded-full bg-slate-400 animate-pulse" />
        <span>{label || 'Checking...'}</span>
      </Badge>
    );
  }

  if (status === 'healthy') {
    return (
      <Badge variant="success" className="gap-1.5 py-1">
        <span className="h-2 w-2 rounded-full bg-emerald-400 animate-pulse" />
        <span>{label || 'Operational'}</span>
      </Badge>
    );
  }

  if (status === 'degraded') {
    return (
      <Badge variant="warning" className="gap-1.5 py-1">
        <span className="h-2 w-2 rounded-full bg-amber-400" />
        <span>{label || 'Degraded'}</span>
      </Badge>
    );
  }

  if (status === 'disabled') {
    return (
      <Badge variant="secondary" className="gap-1.5 py-1">
        <span className="h-2 w-2 rounded-full bg-slate-500" />
        <span>{label || 'Disabled'}</span>
      </Badge>
    );
  }

  return (
    <Badge variant="destructive" className="gap-1.5 py-1">
      <span className="h-2 w-2 rounded-full bg-rose-400" />
      <span>{label || 'Offline'}</span>
    </Badge>
  );
}
