import type { LucideIcon } from 'lucide-react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { cn } from '@/lib/utils';

export interface MetricCardProps {
  title: string;
  value?: string | number | null;
  placeholder?: string;
  subtitle: string;
  icon: LucideIcon;
  badge?: string;
  badgeVariant?: 'default' | 'success' | 'warning' | 'purple' | 'cyan' | 'secondary';
  className?: string;
}

export function MetricCard({
  title,
  value,
  placeholder = '--',
  subtitle,
  icon: Icon,
  badge,
  badgeVariant = 'secondary',
  className,
}: MetricCardProps) {
  const displayValue = value !== undefined && value !== null ? value : placeholder;
  const isUnavailable = displayValue === '--';

  return (
    <Card className={cn('transition-all duration-200 hover:border-blue-300 hover:shadow-xs rounded-2xl bg-white border border-slate-200 shadow-2xs dark:bg-slate-900 dark:border-slate-800', className)}>
      <CardHeader className="flex flex-row items-center justify-between pb-2">
        <CardTitle className="text-xs font-semibold text-slate-500 uppercase tracking-wider">
          {title}
        </CardTitle>
        <div className="flex h-8 w-8 items-center justify-center rounded-xl bg-blue-50 text-blue-600 dark:bg-blue-900/30 dark:text-blue-400">
          <Icon className="h-4 w-4" />
        </div>
      </CardHeader>
      <CardContent>
        <div className="flex items-baseline justify-between gap-2">
          <div className={cn('text-2xl font-bold tracking-tight', isUnavailable ? 'text-slate-400 font-mono' : 'text-slate-900 dark:text-slate-100')}>
            {displayValue}
          </div>
          {badge && (
            <Badge variant={badgeVariant} size="sm">
              {badge}
            </Badge>
          )}
        </div>
        <p className="mt-1 text-xs text-slate-500 dark:text-slate-400">
          {subtitle}
        </p>
      </CardContent>
    </Card>
  );
}
