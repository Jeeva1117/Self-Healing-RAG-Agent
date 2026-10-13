import * as React from 'react';
import { cn } from '@/lib/utils';

export interface BadgeProps extends React.HTMLAttributes<HTMLDivElement> {
  variant?: 'default' | 'secondary' | 'success' | 'warning' | 'destructive' | 'outline' | 'purple' | 'cyan';
  size?: 'sm' | 'md';
}

export function Badge({ className, variant = 'default', size = 'md', ...props }: BadgeProps) {
  const variants = {
    default:
      'bg-indigo-500/15 text-indigo-300 border-indigo-500/30 light:bg-indigo-50 light:text-indigo-700 light:border-indigo-200',
    secondary:
      'bg-slate-800 text-slate-300 border-slate-700 light:bg-slate-100 light:text-slate-700 light:border-slate-200',
    success:
      'bg-emerald-500/15 text-emerald-400 border-emerald-500/30 light:bg-emerald-50 light:text-emerald-700 light:border-emerald-200',
    warning:
      'bg-amber-500/15 text-amber-400 border-amber-500/30 light:bg-amber-50 light:text-amber-700 light:border-amber-200',
    destructive:
      'bg-rose-500/15 text-rose-400 border-rose-500/30 light:bg-rose-50 light:text-rose-700 light:border-rose-200',
    outline:
      'border-slate-700 text-slate-300 bg-transparent light:border-slate-300 light:text-slate-600',
    purple:
      'bg-purple-500/15 text-purple-300 border-purple-500/30 light:bg-purple-50 light:text-purple-700 light:border-purple-200',
    cyan:
      'bg-cyan-500/15 text-cyan-300 border-cyan-500/30 light:bg-cyan-50 light:text-cyan-700 light:border-cyan-200',
  };

  const sizes = {
    sm: 'px-1.5 py-0.2 text-[10px]',
    md: 'px-2.5 py-0.5 text-xs',
  };

  return (
    <div
      className={cn(
        'inline-flex items-center gap-1 rounded-md border font-medium transition-colors select-none',
        variants[variant],
        sizes[size],
        className
      )}
      {...props}
    />
  );
}
