import { Link, useLocation } from 'react-router-dom';
import {
  ChevronLeft,
  ChevronRight,
  Sparkles,
} from 'lucide-react';
import { PRIMARY_NAV_ITEMS } from '@/constants/navigation';
import { Tooltip } from '@/components/ui/tooltip';
import { cn } from '@/lib/utils';

interface SidebarProps {
  collapsed: boolean;
  onToggleCollapse: () => void;
}

export function Sidebar({ collapsed, onToggleCollapse }: SidebarProps) {
  const location = useLocation();

  return (
    <aside
      className={cn(
        'hidden md:flex flex-col border-r border-slate-800/80 bg-[#0F172A] text-slate-200 transition-all duration-300 select-none z-30',
        collapsed ? 'w-20' : 'w-64'
      )}
    >
      {/* Brand Header */}
      <div className="flex h-16 items-center justify-between px-4 border-b border-slate-800">
        <Link to="/chat" className="flex items-center gap-3 overflow-hidden group">
          <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-xl bg-blue-600 text-white shadow-md shadow-blue-500/25">
            <Sparkles className="h-5 w-5" />
          </div>
          {!collapsed && (
            <div className="flex flex-col truncate">
              <span className="font-bold text-sm text-white tracking-tight flex items-center gap-1.5">
                Self-Healing RAG
              </span>
              <span className="text-[11px] text-slate-400 font-medium tracking-tight">
                Smarter Retrieval. Better Answers.
              </span>
            </div>
          )}
        </Link>
        <button
          onClick={onToggleCollapse}
          className="rounded-lg p-1.5 text-slate-400 hover:bg-slate-800 hover:text-white transition-colors cursor-pointer"
          aria-label={collapsed ? 'Expand sidebar' : 'Collapse sidebar'}
        >
          {collapsed ? <ChevronRight className="h-4 w-4" /> : <ChevronLeft className="h-4 w-4" />}
        </button>
      </div>

      {/* Nav List */}
      <div className="flex-1 overflow-y-auto py-4 px-3 space-y-1.5">
        {PRIMARY_NAV_ITEMS.map((item) => {
          const isActive =
            location.pathname === item.href ||
            (item.href === '/chat' && location.pathname === '/');
          const Icon = item.icon;

          const linkContent = (
            <Link
              to={item.href}
              className={cn(
                'group flex items-center gap-3 rounded-lg px-3 py-2.5 text-xs font-medium transition-all duration-150',
                isActive
                  ? 'bg-blue-600 text-white font-semibold shadow-sm shadow-blue-500/30'
                  : 'text-slate-400 hover:bg-slate-800/80 hover:text-white'
              )}
            >
              <Icon
                className={cn(
                  'h-4 w-4 shrink-0 transition-colors',
                  isActive ? 'text-white' : 'text-slate-400 group-hover:text-white'
                )}
              />
              {!collapsed && (
                <div className="flex flex-1 items-center justify-between overflow-hidden">
                  <span className="truncate">{item.name}</span>
                </div>
              )}
            </Link>
          );

          return collapsed ? (
            <Tooltip key={item.href} content={item.name} side="right">
              {linkContent}
            </Tooltip>
          ) : (
            <div key={item.href}>{linkContent}</div>
          );
        })}
      </div>

      {/* Footer User Profile */}
      <div className="p-3 border-t border-slate-800">
        <div className="flex items-center gap-3 rounded-xl bg-slate-900/80 p-2.5 border border-slate-800/80">
          <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-blue-600 text-white font-bold text-xs shadow-sm">
            J
          </div>
          {!collapsed && (
            <div className="flex flex-col truncate">
              <span className="font-semibold text-xs text-white">Jeeva</span>
              <span className="text-[11px] text-slate-400">Developer</span>
            </div>
          )}
        </div>
      </div>
    </aside>
  );
}
