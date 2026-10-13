import { useState } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import {
  Bell,
  Menu,
  Moon,
  Search,
  Sun,
  CheckCircle2,
  Database,
  Server,
  Layers,
  ChevronDown,
  LogOut,
  Shield,
  User as UserIcon,
} from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Breadcrumbs, type BreadcrumbItem } from '@/components/ui/breadcrumb';
import { StatusBadge } from '@/components/common/StatusBadge';
import { useSystemHealth } from '@/hooks/useHealth';
import { useTheme } from '@/context/ThemeContext';
import { useToast } from '@/context/ToastContext';
import { useAuth } from '@/context/AuthContext';
import { ALL_NAV_ITEMS } from '@/constants/navigation';

interface HeaderProps {
  onToggleMobileMenu: () => void;
  onOpenCommandPalette: () => void;
}

export function Header({ onToggleMobileMenu, onOpenCommandPalette }: HeaderProps) {
  const location = useLocation();
  const navigate = useNavigate();
  const { theme, toggleTheme } = useTheme();
  const { toast } = useToast();
  const { user, logout } = useAuth();
  const { health, readiness, isLoading, isError } = useSystemHealth();

  const [showStatusPopover, setShowStatusPopover] = useState(false);
  const [showNotifications, setShowNotifications] = useState(false);
  const [showUserMenu, setShowUserMenu] = useState(false);

  const handleLogout = async () => {
    setShowUserMenu(false);
    await logout();
    toast.info('Signed out successfully');
    navigate('/login', { replace: true });
  };

  // Compute current page breadcrumbs
  const currentItem = ALL_NAV_ITEMS.find((item) => item.href === location.pathname);
  const breadcrumbs: BreadcrumbItem[] = [
    { label: 'Workspace', href: '/chat' },
    { label: currentItem ? currentItem.name : 'AI Chat' },
  ];

  const getHealthStatus = () => {
    if (isLoading) return 'loading';
    if (isError || !health) return 'unhealthy';
    return health.status === 'ok' ? 'healthy' : 'degraded';
  };

  return (
    <header className="sticky top-0 z-20 flex h-16 w-full items-center justify-between border-b border-slate-200 bg-white px-4 md:px-6 shadow-sm transition-colors dark:bg-[#0B0F19] dark:border-slate-800">
      {/* Left: Mobile Toggle & Breadcrumbs */}
      <div className="flex items-center gap-3">
        <button
          onClick={onToggleMobileMenu}
          className="md:hidden rounded-lg p-2 text-slate-500 hover:bg-slate-100 hover:text-slate-900 dark:text-slate-400 dark:hover:bg-slate-900 cursor-pointer"
          aria-label="Open navigation menu"
        >
          <Menu className="h-5 w-5" />
        </button>

        <Breadcrumbs items={breadcrumbs} />
      </div>

      {/* Center: Search Bar Trigger */}
      <div className="flex-1 max-w-lg mx-4 hidden sm:block">
        <button
          type="button"
          onClick={onOpenCommandPalette}
          className="flex w-full items-center justify-between rounded-xl border border-slate-200 bg-slate-50/80 px-3.5 py-2 text-xs text-slate-500 hover:border-blue-300 hover:bg-white hover:text-slate-800 transition-all shadow-inner dark:bg-slate-900/60 dark:border-slate-800 dark:text-slate-400 dark:hover:border-slate-700 cursor-pointer"
        >
          <div className="flex items-center gap-2.5 truncate">
            <Search className="h-4 w-4 text-slate-400" />
            <span className="truncate">Search documents, ask questions, or explore...</span>
          </div>
          <kbd className="inline-flex items-center gap-0.5 rounded-md bg-white px-2 py-0.5 text-[10px] font-mono text-slate-500 border border-slate-200 shadow-2xs dark:bg-slate-800 dark:border-slate-700 dark:text-slate-400">
            Ctrl K
          </kbd>
        </button>
      </div>

      {/* Right Controls */}
      <div className="flex items-center gap-2 sm:gap-3">
        {/* Real-time System Status Probe */}
        <div className="relative">
          <button
            onClick={() => setShowStatusPopover(!showStatusPopover)}
            className="flex items-center gap-1.5 rounded-lg border border-slate-200 bg-slate-50 px-2.5 py-1.5 text-xs text-slate-700 hover:bg-slate-100 dark:bg-slate-900/60 dark:border-slate-800 dark:text-slate-300 transition-colors cursor-pointer select-none"
            aria-label="Toggle system health details"
          >
            <StatusBadge
              status={getHealthStatus()}
              label={health ? `API v${health.version}` : 'Connecting...'}
            />
            <ChevronDown className="h-3 w-3 text-slate-400" />
          </button>

          {/* Status Popover Panel */}
          {showStatusPopover && (
            <div className="absolute right-0 mt-2 w-72 rounded-xl border border-slate-200 bg-white p-4 text-xs shadow-xl z-50 animate-in fade-in-50 zoom-in-95 dark:bg-slate-900 dark:border-slate-800">
              <div className="flex items-center justify-between pb-3 border-b border-slate-200 dark:border-slate-800">
                <span className="font-semibold text-slate-900 dark:text-slate-100">System Infrastructure</span>
                <span className="text-[10px] text-slate-500 font-mono">Live Probes</span>
              </div>
              <div className="mt-3 space-y-2.5">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2 text-slate-700 dark:text-slate-300">
                    <Server className="h-3.5 w-3.5 text-blue-600" />
                    <span>FastAPI Gateway</span>
                  </div>
                  <span className="text-[11px] font-medium text-emerald-600 dark:text-emerald-400">
                    {health ? 'Operational' : 'Connecting'}
                  </span>
                </div>
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2 text-slate-700 dark:text-slate-300">
                    <Database className="h-3.5 w-3.5 text-blue-500" />
                    <span>PostgreSQL / pgvector</span>
                  </div>
                  <span
                    className={`text-[11px] font-medium ${
                      readiness?.dependencies.database.connected
                        ? 'text-emerald-600 dark:text-emerald-400'
                        : 'text-slate-500'
                    }`}
                  >
                    {readiness?.dependencies.database.connected ? 'Connected' : 'Offline / Standby'}
                  </span>
                </div>
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2 text-slate-700 dark:text-slate-300">
                    <Layers className="h-3.5 w-3.5 text-purple-500" />
                    <span>Redis Cache</span>
                  </div>
                  <span
                    className={`text-[11px] font-medium ${
                      readiness?.dependencies.redis.connected
                        ? 'text-emerald-600 dark:text-emerald-400'
                        : 'text-slate-500'
                    }`}
                  >
                    {readiness?.dependencies.redis.connected ? 'Connected' : 'Offline / Standby'}
                  </span>
                </div>
              </div>
              <div className="mt-3 pt-2.5 border-t border-slate-200 dark:border-slate-800 text-[10px] text-slate-500 flex justify-between">
                <span>Polling every 15s</span>
                <button
                  onClick={() => setShowStatusPopover(false)}
                  className="text-blue-600 hover:underline cursor-pointer"
                >
                  Close
                </button>
              </div>
            </div>
          )}
        </div>

        {/* Notifications */}
        <div className="relative">
          <Button
            variant="ghost"
            size="icon"
            onClick={() => setShowNotifications(!showNotifications)}
            className="relative text-slate-500 hover:text-slate-900 hover:bg-slate-100 dark:text-slate-400 dark:hover:text-slate-100 dark:hover:bg-slate-800"
            title="Notifications"
          >
            <Bell className="h-4 w-4" />
            <span className="absolute top-2 right-2 h-1.5 w-1.5 rounded-full bg-blue-600" />
          </Button>

          {showNotifications && (
            <div className="absolute right-0 mt-2 w-80 rounded-xl border border-slate-200 bg-white p-4 text-xs shadow-xl z-50 animate-in fade-in-50 zoom-in-95 dark:bg-slate-900 dark:border-slate-800">
              <div className="flex items-center justify-between pb-3 border-b border-slate-200 dark:border-slate-800">
                <span className="font-semibold text-slate-900 dark:text-slate-100">Notifications</span>
                <span className="text-[10px] text-slate-500">0 unread</span>
              </div>
              <div className="py-6 text-center text-slate-500">
                <CheckCircle2 className="h-6 w-6 text-slate-400 mx-auto mb-2" />
                <p className="font-medium text-slate-700 dark:text-slate-300">All caught up!</p>
                <p className="text-[11px] text-slate-500 mt-1">
                  System alerts and evaluation notifications will appear here.
                </p>
              </div>
            </div>
          )}
        </div>

        {/* Theme Toggle */}
        <Button
          variant="ghost"
          size="icon"
          onClick={() => {
            toggleTheme();
            toast.info(`Switched to ${theme === 'dark' ? 'Light' : 'Dark'} mode`);
          }}
          className="text-slate-500 hover:text-slate-900 hover:bg-slate-100 dark:text-slate-400 dark:hover:text-slate-100 dark:hover:bg-slate-800"
          title={`Switch to ${theme === 'dark' ? 'Light' : 'Dark'} mode`}
        >
          {theme === 'dark' ? <Sun className="h-4 w-4" /> : <Moon className="h-4 w-4" />}
        </Button>

        {/* Real Authenticated User Profile + Dropdown */}
        <div className="relative pl-1 border-l border-slate-200 dark:border-slate-800">
          <button
            onClick={() => setShowUserMenu(!showUserMenu)}
            className="flex items-center gap-2.5 rounded-lg p-1.5 hover:bg-slate-100 dark:hover:bg-slate-800 transition-colors cursor-pointer select-none"
            aria-label="User profile menu"
          >
            <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-blue-600 text-white font-bold text-xs shadow-xs uppercase">
              {user?.name?.[0] || 'U'}
            </div>
            <div className="hidden lg:flex flex-col text-left">
              <div className="flex items-center gap-1">
                <span className="text-xs font-semibold text-slate-900 dark:text-slate-100 truncate max-w-[120px]">
                  {user?.name || 'User'}
                </span>
                {user?.email === 'demo@selfhealingrag.local' && (
                  <span className="px-1 py-0.5 rounded text-[9px] font-bold bg-amber-100 text-amber-800 dark:bg-amber-900/40 dark:text-amber-300">
                    DEMO
                  </span>
                )}
              </div>
              <span className="text-[10px] text-slate-500 font-medium">
                {user?.role || 'USER'}
              </span>
            </div>
            <ChevronDown className="h-3 w-3 text-slate-400" />
          </button>

          {showUserMenu && (
            <div className="absolute right-0 mt-2 w-60 rounded-xl border border-slate-200 bg-white p-2 text-xs shadow-xl z-50 animate-in fade-in-50 zoom-in-95 dark:bg-slate-900 dark:border-slate-800">
              <div className="px-3 py-2 border-b border-slate-100 dark:border-slate-800">
                <p className="font-semibold text-slate-900 dark:text-slate-100 truncate">
                  {user?.name || 'User'}
                </p>
                <p className="text-[10px] text-slate-500 truncate">
                  {user?.email || 'user@company.com'}
                </p>
                <div className="mt-1 flex items-center gap-1.5">
                  <span className="inline-block px-1.5 py-0.5 rounded text-[10px] font-semibold bg-blue-50 text-blue-700 dark:bg-blue-900/30 dark:text-blue-300">
                    {user?.role || 'USER'}
                  </span>
                  {user?.email === 'demo@selfhealingrag.local' && (
                    <span className="inline-block px-1.5 py-0.5 rounded text-[10px] font-bold bg-amber-100 text-amber-800 dark:bg-amber-900/40 dark:text-amber-300">
                      DEMO
                    </span>
                  )}
                  {user?.is_active && (
                    <span className="inline-block px-1.5 py-0.5 rounded text-[10px] font-semibold bg-emerald-50 text-emerald-700 dark:bg-emerald-900/30 dark:text-emerald-300">
                      Active
                    </span>
                  )}
                </div>
              </div>
              <div className="py-1">
                <button
                  onClick={() => {
                    setShowUserMenu(false);
                    navigate('/settings');
                  }}
                  className="w-full flex items-center gap-2 text-left px-3 py-1.5 rounded-lg hover:bg-slate-100 text-slate-700 dark:text-slate-300 dark:hover:bg-slate-800 cursor-pointer"
                >
                  <UserIcon className="h-3.5 w-3.5 text-slate-400" />
                  <span>Account & Profile</span>
                </button>
                <button
                  onClick={() => {
                    setShowUserMenu(false);
                    navigate('/settings/security');
                  }}
                  className="w-full flex items-center gap-2 text-left px-3 py-1.5 rounded-lg hover:bg-slate-100 text-slate-700 dark:text-slate-300 dark:hover:bg-slate-800 cursor-pointer"
                >
                  <Shield className="h-3.5 w-3.5 text-slate-400" />
                  <span>Security & Sessions</span>
                </button>
                <button
                  onClick={() => {
                    setShowUserMenu(false);
                    onOpenCommandPalette();
                  }}
                  className="w-full flex items-center gap-2 text-left px-3 py-1.5 rounded-lg hover:bg-slate-100 text-slate-700 dark:text-slate-300 dark:hover:bg-slate-800 cursor-pointer"
                >
                  <Search className="h-3.5 w-3.5 text-slate-400" />
                  <span>Command Palette (Ctrl+K)</span>
                </button>
              </div>
              <div className="pt-1 border-t border-slate-100 dark:border-slate-800">
                <button
                  onClick={handleLogout}
                  className="w-full flex items-center gap-2 text-left px-3 py-1.5 rounded-lg hover:bg-rose-50 text-rose-600 dark:hover:bg-rose-950/30 dark:text-rose-400 font-medium cursor-pointer"
                >
                  <LogOut className="h-3.5 w-3.5" />
                  <span>Sign Out</span>
                </button>
              </div>
            </div>
          )}
        </div>
      </div>
    </header>
  );
}
