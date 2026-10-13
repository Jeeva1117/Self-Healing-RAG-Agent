import { ShieldCheck, AlertCircle } from 'lucide-react';
import { Badge } from '@/components/ui/badge';
import { cn } from '@/lib/utils';

export interface ConfidenceIndicatorProps {
  score?: number | null; // Value between 0.0 and 1.0 or 0 to 100
  label?: string;
  className?: string;
}

export function ConfidenceIndicator({ score, label, className }: ConfidenceIndicatorProps) {
  if (score === undefined || score === null) {
    return (
      <div className={cn('inline-flex items-center gap-1.5 text-xs text-slate-500 light:text-slate-400 select-none', className)}>
        <AlertCircle className="h-3.5 w-3.5 text-slate-500" />
        <span className="font-mono text-[11px]">Confidence unavailable</span>
      </div>
    );
  }

  // Normalize to 0-100 percentage
  const percentage = score <= 1.0 ? Math.round(score * 100) : Math.round(score);

  let variant: 'success' | 'warning' | 'destructive' = 'success';
  let defaultLabel = 'High confidence';

  if (percentage < 60) {
    variant = 'destructive';
    defaultLabel = 'Low confidence';
  } else if (percentage < 85) {
    variant = 'warning';
    defaultLabel = 'Moderate confidence';
  }

  return (
    <div className={cn('inline-flex items-center gap-2 select-none', className)}>
      <Badge variant={variant} size="sm" className="font-mono gap-1">
        <ShieldCheck className="h-3 w-3" />
        <span>{percentage}%</span>
      </Badge>
      <span className="text-xs text-slate-400 light:text-slate-600">
        {label || defaultLabel}
      </span>
    </div>
  );
}
