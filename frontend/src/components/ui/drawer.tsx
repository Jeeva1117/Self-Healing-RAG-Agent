import * as React from 'react';
import { X } from 'lucide-react';
import { cn } from '@/lib/utils';

export interface DrawerProps {
  open: boolean;
  onClose: () => void;
  title?: React.ReactNode;
  description?: React.ReactNode;
  children: React.ReactNode;
  width?: 'md' | 'lg' | 'xl';
}

export function Drawer({
  open,
  onClose,
  title,
  description,
  children,
  width = 'lg',
}: DrawerProps) {
  React.useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose();
    };
    if (open) {
      document.body.style.overflow = 'hidden';
      window.addEventListener('keydown', handleKeyDown);
    }
    return () => {
      document.body.style.overflow = 'unset';
      window.removeEventListener('keydown', handleKeyDown);
    };
  }, [open, onClose]);

  if (!open) return null;

  const widths = {
    md: 'max-w-md',
    lg: 'max-w-lg',
    xl: 'max-w-2xl',
  };

  return (
    <div className="fixed inset-0 z-50 overflow-hidden" role="dialog" aria-modal="true">
      {/* Backdrop */}
      <div
        className="fixed inset-0 bg-black/60 backdrop-blur-sm transition-opacity animate-in fade-in"
        onClick={onClose}
      />

      <div className="fixed inset-y-0 right-0 flex max-w-full pl-10">
        <div
          className={cn(
            'w-screen border-l border-slate-800 bg-slate-950 p-6 text-slate-100 shadow-2xl transition-all animate-in slide-in-from-right duration-200 overflow-y-auto light:bg-white light:border-slate-200 light:text-slate-900',
            widths[width]
          )}
        >
          <div className="flex items-start justify-between pb-4 border-b border-slate-800/80 light:border-slate-100">
            <div>
              {title && <h2 className="text-base font-semibold leading-none tracking-tight">{title}</h2>}
              {description && <p className="mt-1.5 text-xs text-slate-400 light:text-slate-500">{description}</p>}
            </div>
            <button
              onClick={onClose}
              className="rounded-lg p-1.5 text-slate-400 hover:bg-slate-800 hover:text-slate-200 light:hover:bg-slate-100 light:hover:text-slate-700 transition-colors cursor-pointer"
              aria-label="Close panel"
            >
              <X className="h-4 w-4" />
            </button>
          </div>

          <div className="pt-4">{children}</div>
        </div>
      </div>
    </div>
  );
}
