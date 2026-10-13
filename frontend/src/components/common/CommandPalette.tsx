import React, { useState, useEffect, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  LayoutDashboard,
  MessageSquare,
  BookOpen,
  Database,
  Search,
  Network,
  CheckCircle2,
  Activity,
  Settings,
  Sun,
  Moon,
  Upload,
} from 'lucide-react';
import { useTheme } from '@/context/ThemeContext';
import { useToast } from '@/context/ToastContext';
import { cn } from '@/lib/utils';

interface CommandItem {
  id: string;
  title: string;
  subtitle: string;
  icon: React.ComponentType<{ className?: string }>;
  category: 'Navigation' | 'Actions' | 'System';
  action: () => void;
  shortcut?: string;
}

export function CommandPalette({
  open,
  onClose,
  onOpenUpload,
}: {
  open: boolean;
  onClose: () => void;
  onOpenUpload?: () => void;
}) {
  const navigate = useNavigate();
  const { theme, toggleTheme } = useTheme();
  const { toast } = useToast();
  const [query, setQuery] = useState('');
  const [selectedIndex, setSelectedIndex] = useState(0);
  const inputRef = useRef<HTMLInputElement>(null);

  const commands: CommandItem[] = [
    {
      id: 'dashboard',
      title: 'Dashboard',
      subtitle: 'System overview & architecture topology',
      icon: LayoutDashboard,
      category: 'Navigation',
      action: () => { navigate('/dashboard'); onClose(); },
      shortcut: 'G D',
    },
    {
      id: 'chat',
      title: 'AI Chat',
      subtitle: 'Ask questions with verified citations',
      icon: MessageSquare,
      category: 'Navigation',
      action: () => { navigate('/chat'); onClose(); },
      shortcut: 'G C',
    },
    {
      id: 'kb',
      title: 'Knowledge Base',
      subtitle: 'Manage indexed documents & collections',
      icon: BookOpen,
      category: 'Navigation',
      action: () => { navigate('/knowledge-base'); onClose(); },
      shortcut: 'G K',
    },
    {
      id: 'sources',
      title: 'Data Sources',
      subtitle: 'Configure external data connectors',
      icon: Database,
      category: 'Navigation',
      action: () => { navigate('/data-sources'); onClose(); },
    },
    {
      id: 'search',
      title: 'Search Playground',
      subtitle: 'Test BM25, vector, and hybrid search',
      icon: Search,
      category: 'Navigation',
      action: () => { navigate('/search'); onClose(); },
      shortcut: 'G S',
    },
    {
      id: 'workflows',
      title: 'Agent Workflows',
      subtitle: 'Inspect LangGraph cyclic state graph',
      icon: Network,
      category: 'Navigation',
      action: () => { navigate('/agent-workflows'); onClose(); },
      shortcut: 'G W',
    },
    {
      id: 'evaluation',
      title: 'Evaluation',
      subtitle: 'RAGAS & DeepEval quality benchmarks',
      icon: CheckCircle2,
      category: 'Navigation',
      action: () => { navigate('/evaluation'); onClose(); },
      shortcut: 'G E',
    },
    {
      id: 'observability',
      title: 'Observability',
      subtitle: 'Distributed OpenTelemetry traces & spans',
      icon: Activity,
      category: 'Navigation',
      action: () => { navigate('/observability'); onClose(); },
      shortcut: 'G O',
    },
    {
      id: 'settings',
      title: 'Settings',
      subtitle: 'Configure workspace, models, & security',
      icon: Settings,
      category: 'Navigation',
      action: () => { navigate('/settings'); onClose(); },
    },
    {
      id: 'upload',
      title: 'Upload Document',
      subtitle: 'Add new knowledge source to the platform',
      icon: Upload,
      category: 'Actions',
      action: () => {
        onClose();
        if (onOpenUpload) onOpenUpload();
        else navigate('/knowledge-base');
      },
      shortcut: 'U',
    },
    {
      id: 'theme',
      title: `Toggle Theme (Currently ${theme === 'dark' ? 'Dark' : 'Light'})`,
      subtitle: `Switch to ${theme === 'dark' ? 'light' : 'dark'} mode`,
      icon: theme === 'dark' ? Sun : Moon,
      category: 'System',
      action: () => {
        toggleTheme();
        toast.info(`Switched to ${theme === 'dark' ? 'Light' : 'Dark'} mode`);
        onClose();
      },
      shortcut: 'T',
    },
  ];

  const filtered = commands.filter((cmd) => {
    const q = query.toLowerCase();
    return (
      cmd.title.toLowerCase().includes(q) ||
      cmd.subtitle.toLowerCase().includes(q) ||
      cmd.category.toLowerCase().includes(q)
    );
  });

  useEffect(() => {
    if (open) {
      const t = setTimeout(() => inputRef.current?.focus(), 50);
      return () => clearTimeout(t);
    }
  }, [open]);

  useEffect(() => {
    if (!open) return;

    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        e.preventDefault();
        onClose();
      } else if (e.key === 'ArrowDown') {
        e.preventDefault();
        setSelectedIndex((prev) => (prev + 1) % (filtered.length || 1));
      } else if (e.key === 'ArrowUp') {
        e.preventDefault();
        setSelectedIndex((prev) => (prev - 1 + (filtered.length || 1)) % (filtered.length || 1));
      } else if (e.key === 'Enter') {
        e.preventDefault();
        if (filtered[selectedIndex]) {
          filtered[selectedIndex].action();
        }
      }
    };

    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [open, filtered, selectedIndex, onClose]);

  if (!open) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-start justify-center pt-20 p-4 sm:p-6" role="dialog" aria-modal="true">
      {/* Backdrop */}
      <div
        className="fixed inset-0 bg-black/70 backdrop-blur-sm transition-opacity animate-in fade-in"
        onClick={onClose}
      />

      {/* Palette Container */}
      <div className="relative w-full max-w-xl rounded-2xl border border-slate-200 bg-white shadow-2xl overflow-hidden transition-all animate-in zoom-in-95 dark:bg-slate-900 dark:border-slate-800">
        {/* Search Input */}
        <div className="flex items-center px-4 border-b border-slate-200 dark:border-slate-800">
          <Search className="h-4 w-4 text-blue-600 mr-3 shrink-0" />
          <input
            ref={inputRef}
            type="text"
            value={query}
            onChange={(e) => {
              setQuery(e.target.value);
              setSelectedIndex(0);
            }}
            placeholder="Search documents, commands, workspaces... (Type to filter)"
            className="h-12 w-full bg-transparent text-sm text-slate-900 placeholder:text-slate-400 focus:outline-none dark:text-slate-100"
          />
          <kbd className="hidden sm:inline-flex items-center gap-1 rounded bg-slate-100 px-2 py-0.5 text-[10px] text-slate-600 font-mono border border-slate-200 dark:bg-slate-800 dark:border-slate-700 dark:text-slate-400">
            ESC
          </kbd>
        </div>

        {/* Command List */}
        <div className="max-h-80 overflow-y-auto p-2">
          {filtered.length === 0 ? (
            <div className="py-8 text-center text-xs text-slate-500">
              No matching commands or destinations found.
            </div>
          ) : (
            filtered.map((cmd, idx) => {
              const isSelected = idx === selectedIndex;
              const Icon = cmd.icon;

              return (
                <div
                  key={cmd.id}
                  onClick={() => cmd.action()}
                  onMouseEnter={() => setSelectedIndex(idx)}
                  className={cn(
                    'flex items-center justify-between px-3 py-2.5 rounded-xl text-xs cursor-pointer transition-colors select-none',
                    isSelected
                      ? 'bg-blue-50 text-blue-900 border border-blue-200 font-semibold dark:bg-blue-950/40 dark:text-blue-200 dark:border-blue-800'
                      : 'text-slate-700 hover:bg-slate-50 dark:text-slate-300 dark:hover:bg-slate-800/50'
                  )}
                >
                  <div className="flex items-center gap-3">
                    <div
                      className={cn(
                        'flex h-7 w-7 items-center justify-center rounded-lg border',
                        isSelected
                          ? 'bg-blue-600 text-white border-blue-600'
                          : 'bg-slate-100 text-slate-500 border-slate-200 dark:bg-slate-800 dark:text-slate-400 dark:border-slate-700'
                      )}
                    >
                      <Icon className="h-4 w-4" />
                    </div>
                    <div>
                      <div className="font-semibold">{cmd.title}</div>
                      <div className="text-[11px] text-slate-500 dark:text-slate-400">
                        {cmd.subtitle}
                      </div>
                    </div>
                  </div>

                  <div className="flex items-center gap-2">
                    <span className="text-[10px] font-mono text-slate-400 uppercase tracking-wider">
                      {cmd.category}
                    </span>
                    {cmd.shortcut && (
                      <kbd className="hidden sm:inline-flex rounded bg-slate-100 px-1.5 py-0.5 text-[10px] text-slate-500 font-mono border border-slate-200 dark:bg-slate-800 dark:border-slate-700 dark:text-slate-400">
                        {cmd.shortcut}
                      </kbd>
                    )}
                  </div>
                </div>
              );
            })
          )}
        </div>

        {/* Footer shortcuts */}
        <div className="flex items-center justify-between px-4 py-2 bg-slate-50 border-t border-slate-200 text-[11px] text-slate-500 dark:bg-slate-950/80 dark:border-slate-800">
          <div className="flex items-center gap-3">
            <span>↑↓ Navigate</span>
            <span>↵ Select</span>
            <span>esc Close</span>
          </div>
          <span className="font-mono text-[10px] text-blue-600 dark:text-blue-400 font-semibold">Self-Healing RAG Engine</span>
        </div>
      </div>
    </div>
  );
}
