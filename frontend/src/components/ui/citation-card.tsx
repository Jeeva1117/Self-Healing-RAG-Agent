import { FileText, ExternalLink } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { cn } from '@/lib/utils';

export interface CitationItem {
  id: number;
  title: string;
  section?: string;
  page?: number | string;
  snippet: string;
  relevanceScore?: number;
  documentId?: string;
}

export function CitationPill({
  id,
  onClick,
}: {
  id: number;
  onClick?: () => void;
}) {
  return (
    <button
      onClick={onClick}
      type="button"
      className="inline-flex items-center justify-center h-4.5 px-1.5 rounded bg-blue-50 text-blue-700 border border-blue-200 text-[10px] font-mono font-bold align-super ml-1 hover:bg-blue-100 hover:text-blue-800 transition-colors cursor-pointer select-none dark:bg-blue-900/30 dark:text-blue-300 dark:border-blue-700"
      title={`Source [${id}]`}
    >
      [{id}]
    </button>
  );
}

export function CitationCard({
  citation,
  onOpenSnippet,
  className,
}: {
  citation: CitationItem;
  onOpenSnippet?: (item: CitationItem) => void;
  className?: string;
}) {
  return (
    <div
      className={cn(
        'group flex items-center justify-between gap-3 p-3 rounded-xl border border-slate-200 bg-white shadow-2xs hover:border-blue-300 hover:shadow-xs transition-all dark:bg-slate-900 dark:border-slate-800 dark:hover:border-blue-600',
        className
      )}
    >
      <div className="flex items-center gap-3 overflow-hidden">
        {/* Blue document icon */}
        <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-blue-50 text-blue-600 dark:bg-blue-900/30 dark:text-blue-400">
          <FileText className="h-4.5 w-4.5" />
        </div>
        <div className="flex flex-col truncate">
          <div className="flex items-center gap-1.5">
            <span className="font-semibold text-xs text-slate-900 dark:text-slate-100 truncate">
              {citation.title}
            </span>
          </div>
          <div className="text-[11px] text-slate-500 dark:text-slate-400 truncate">
            {citation.page ? `Page ${citation.page}` : ''}
            {citation.page && citation.section ? ' · ' : ''}
            {citation.section || ''}
          </div>
        </div>
      </div>

      <Button
        variant="outline"
        size="xs"
        onClick={() => onOpenSnippet?.(citation)}
        className="shrink-0 gap-1 text-[11px] text-blue-600 border-blue-200 bg-blue-50/50 hover:bg-blue-100 hover:text-blue-700 hover:border-blue-300 dark:bg-blue-900/20 dark:border-blue-800 dark:text-blue-300"
      >
        <span>View</span>
        <ExternalLink className="h-3 w-3" />
      </Button>
    </div>
  );
}
