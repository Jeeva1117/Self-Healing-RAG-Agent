import { Link } from 'react-router-dom';
import { ChevronRight } from 'lucide-react';
import { cn } from '@/lib/utils';

export interface BreadcrumbItem {
  label: string;
  href?: string;
}

export function Breadcrumbs({ items, className }: { items: BreadcrumbItem[]; className?: string }) {
  return (
    <nav aria-label="Breadcrumb" className={cn('flex items-center space-x-1.5 text-xs text-slate-400 light:text-slate-500', className)}>
      {items.map((item, index) => {
        const isLast = index === items.length - 1;

        return (
          <div key={index} className="flex items-center space-x-1.5">
            {index > 0 && <ChevronRight className="h-3 w-3 text-slate-600 light:text-slate-400" />}
            {item.href && !isLast ? (
              <Link
                to={item.href}
                className="hover:text-slate-200 light:hover:text-slate-800 transition-colors"
              >
                {item.label}
              </Link>
            ) : (
              <span className={cn(isLast && 'font-medium text-slate-200 light:text-slate-900')}>
                {item.label}
              </span>
            )}
          </div>
        );
      })}
    </nav>
  );
}
