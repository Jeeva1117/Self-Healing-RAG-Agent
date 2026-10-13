import type { LucideIcon } from 'lucide-react';
import { Card } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Link } from 'react-router-dom';

interface EmptyStateProps {
  icon: LucideIcon;
  title: string;
  description: string;
  phaseBadge: string;
  plannedFeatures: string[];
}

export function EmptyState({
  icon: Icon,
  title,
  description,
  phaseBadge,
  plannedFeatures,
}: EmptyStateProps) {
  return (
    <Card className="flex flex-col items-center justify-center p-12 text-center border-dashed border-slate-800 bg-slate-900/30">
      <div className="flex h-16 w-16 items-center justify-center rounded-2xl bg-indigo-500/10 text-indigo-400 mb-5">
        <Icon className="h-8 w-8" />
      </div>

      <div className="flex items-center gap-2 mb-2">
        <h2 className="text-xl font-semibold text-slate-100">{title}</h2>
        <Badge variant="purple">{phaseBadge}</Badge>
      </div>

      <p className="max-w-md text-sm text-slate-400 mb-6 leading-relaxed">
        {description}
      </p>

      <div className="w-full max-w-lg rounded-lg border border-slate-800/80 bg-slate-950/60 p-4 mb-6 text-left">
        <div className="text-xs font-semibold uppercase tracking-wider text-slate-400 mb-2">
          Architecture Roadmap Scope
        </div>
        <ul className="space-y-1.5">
          {plannedFeatures.map((feat, idx) => (
            <li key={idx} className="flex items-start text-xs text-slate-300">
              <span className="text-indigo-400 mr-2 font-mono">•</span>
              <span>{feat}</span>
            </li>
          ))}
        </ul>
      </div>

      <div className="flex items-center gap-3">
        <Link to="/dashboard">
          <Button variant="outline" size="sm">
            Back to Dashboard
          </Button>
        </Link>
        <Link to="/settings">
          <Button variant="ghost" size="sm">
            View Settings
          </Button>
        </Link>
      </div>
    </Card>
  );
}
