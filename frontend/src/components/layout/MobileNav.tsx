import { Link, useLocation } from 'react-router-dom';
import { X, Sparkles } from 'lucide-react';
import { PRIMARY_NAV_ITEMS } from '@/constants/navigation';
import { cn } from '@/lib/utils';

interface MobileNavProps {
  open: boolean;
  onClose: () => void;
}

export function MobileNav({ open, onClose }: MobileNavProps) {
  const location = useLocation();

  if (!open) return null;

  return (
    <div className="fixed inset-0 z-50 flex md:hidden" role="dialog" aria-modal="true">
      {/* Backdrop */}
      <div
        className="fixed inset-0 bg-black/70 backdrop-blur-sm transition-opacity"
        onClick={onClose}
      />

      {/* Drawer */}
      <div className="relative flex w-72 flex-col bg-[#0F172A] p-4 border-r border-slate-800 shadow-2xl z-10 text-white">
        <div className="flex items-center justify-between pb-4 border-b border-slate-800">
          <div className="flex items-center gap-2.5">
            <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-blue-600 text-white font-bold text-xs shadow-sm">
              <Sparkles className="h-4 w-4" />
            </div>
            <div className="flex flex-col">
              <span className="font-bold text-white text-sm">Self-Healing RAG</span>
              <span className="text-[10px] text-slate-400">Smarter Retrieval</span>
            </div>
          </div>
          <button
            onClick={onClose}
            className="rounded-lg p-1.5 text-slate-400 hover:bg-slate-800 hover:text-white cursor-pointer"
            aria-label="Close navigation"
          >
            <X className="h-5 w-5" />
          </button>
        </div>

        <nav className="flex-1 overflow-y-auto py-4 space-y-1.5">
          {PRIMARY_NAV_ITEMS.map((item) => {
            const isActive =
              location.pathname === item.href ||
              (item.href === '/chat' && location.pathname === '/');
            const Icon = item.icon;

            return (
              <Link
                key={item.href}
                to={item.href}
                onClick={onClose}
                className={cn(
                  'flex items-center justify-between rounded-lg px-3 py-2.5 text-xs font-medium transition-colors',
                  isActive
                    ? 'bg-blue-600 text-white font-semibold shadow-sm'
                    : 'text-slate-400 hover:bg-slate-800/80 hover:text-white'
                )}
              >
                <div className="flex items-center gap-3">
                  <Icon className={cn('h-4 w-4 shrink-0', isActive ? 'text-white' : 'text-slate-400')} />
                  <span>{item.name}</span>
                </div>
              </Link>
            );
          })}
        </nav>

        {/* User profile footer */}
        <div className="pt-3 border-t border-slate-800">
          <div className="flex items-center gap-3 rounded-xl bg-slate-900/80 p-2.5 border border-slate-800/80">
            <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-blue-600 text-white font-bold text-xs">
              J
            </div>
            <div className="flex flex-col truncate">
              <span className="font-semibold text-xs text-white">Jeeva</span>
              <span className="text-[11px] text-slate-400">Developer</span>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
