import { AlertCircle } from 'lucide-react';

export function PhaseAlert() {
  return (
    <div className="flex items-center gap-3 rounded-xl border border-blue-200 bg-blue-50/80 px-4 py-2.5 text-xs text-blue-900 shadow-2xs dark:bg-blue-950/40 dark:border-blue-900 dark:text-blue-300">
      <AlertCircle className="h-4 w-4 shrink-0 text-blue-600 dark:text-blue-400" />
      <div>
        <span className="font-semibold text-blue-950 dark:text-blue-200">System Foundation Active: </span>
        <span>
          Architecture layers, async DB session management, Redis abstraction, and real-time backend health probes are operational.
        </span>
      </div>
    </div>
  );
}
