import { useState } from 'react';
import {
  Settings,
  Cpu,
  Search,
  Shield,
  Layers,
  Save,
  Moon,
  Sun,
  User as UserIcon,
  Laptop,
  Trash2,
  Lock,
  CheckCircle2,
  AlertCircle,
  KeyRound,
  LogOut,
} from 'lucide-react';
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Select } from '@/components/ui/select';
import { Badge } from '@/components/ui/badge';
import { Tabs, TabsList, TabsTrigger, TabsContent } from '@/components/ui/tabs';
import { useTheme } from '@/context/ThemeContext';
import { useToast } from '@/context/ToastContext';
import { useAuth } from '@/context/AuthContext';
import { useChangePassword, useRevokeSession, useUserSessions } from '@/hooks/useAuth';
import { ApiError } from '@/services/api';

interface SettingsPageProps {
  defaultTab?: string;
}

export function SettingsPage({ defaultTab = 'profile' }: SettingsPageProps) {
  const { theme, setTheme } = useTheme();
  const { toast } = useToast();
  const { user, logoutAll } = useAuth();

  const [activeTab, setActiveTab] = useState(defaultTab);
  const [workspaceName, setWorkspaceName] = useState('Enterprise Primary Workspace');
  const [llmProvider, setLlmProvider] = useState('openai');
  const [llmModel, setLlmModel] = useState('gpt-4o');
  const [temperature, setTemperature] = useState(0.2);
  const [maxTokens, setMaxTokens] = useState(2048);

  const [topK, setTopK] = useState(5);
  const [similarityThreshold, setSimilarityThreshold] = useState(0.7);
  const [hybridAlpha, setHybridAlpha] = useState(0.5);

  // Change Password State
  const [currentPassword, setCurrentPassword] = useState('');
  const [newPassword, setNewPassword] = useState('');
  const [confirmNewPassword, setConfirmNewPassword] = useState('');
  const [passwordError, setPasswordError] = useState<string | null>(null);

  const changePasswordMutation = useChangePassword();
  const revokeSessionMutation = useRevokeSession();
  const { data: sessions, isLoading: sessionsLoading } = useUserSessions();

  const handleSaveGeneral = (e: React.FormEvent) => {
    e.preventDefault();
    toast.success('Workspace preferences updated');
  };

  const handleChangePassword = async (e: React.FormEvent) => {
    e.preventDefault();
    setPasswordError(null);

    if (newPassword.length < 8) {
      setPasswordError('New password must be at least 8 characters long');
      return;
    }
    if (newPassword !== confirmNewPassword) {
      setPasswordError('New passwords do not match');
      return;
    }

    try {
      await changePasswordMutation.mutateAsync({
        current_password: currentPassword,
        new_password: newPassword,
      });
      toast.success('Password updated successfully. Please log in again.');
      setCurrentPassword('');
      setNewPassword('');
      setConfirmNewPassword('');
    } catch (err: unknown) {
      if (err instanceof ApiError) {
        setPasswordError(err.message);
      } else {
        setPasswordError('Failed to change password. Please verify current credentials.');
      }
    }
  };

  const handleRevokeSession = async (sessionId: string) => {
    try {
      await revokeSessionMutation.mutateAsync(sessionId);
      toast.success('Session revoked successfully');
    } catch {
      toast.error('Failed to revoke session');
    }
  };

  const handleLogoutAll = async () => {
    try {
      await logoutAll();
      toast.info('All sessions revoked. Redirecting...');
      window.location.href = '/login';
    } catch {
      toast.error('Failed to revoke all sessions');
    }
  };

  return (
    <div className="space-y-6">
      {/* Top Header */}
      <div>
        <h1 className="text-2xl font-bold tracking-tight text-slate-900 dark:text-slate-100">
          Platform Settings & Configuration
        </h1>
        <p className="text-xs sm:text-sm text-slate-500 dark:text-slate-400 mt-1">
          Manage identity security, workspace settings, AI model providers, and hybrid retrieval policies.
        </p>
      </div>

      {/* Settings Sections Tabs */}
      <Tabs value={activeTab} onValueChange={setActiveTab}>
        <TabsList className="mb-4 bg-slate-100 p-1 dark:bg-slate-800">
          <TabsTrigger value="profile" className="gap-1.5">
            <UserIcon className="h-3.5 w-3.5" />
            <span>Profile</span>
          </TabsTrigger>
          <TabsTrigger value="security" className="gap-1.5">
            <Shield className="h-3.5 w-3.5" />
            <span>Security & Sessions</span>
          </TabsTrigger>
          <TabsTrigger value="general" className="gap-1.5">
            <Settings className="h-3.5 w-3.5" />
            <span>Workspace</span>
          </TabsTrigger>
          <TabsTrigger value="models" className="gap-1.5">
            <Cpu className="h-3.5 w-3.5" />
            <span>AI Models</span>
          </TabsTrigger>
          <TabsTrigger value="retrieval" className="gap-1.5">
            <Search className="h-3.5 w-3.5" />
            <span>Retrieval</span>
          </TabsTrigger>
          <TabsTrigger value="integrations" className="gap-1.5">
            <Layers className="h-3.5 w-3.5" />
            <span>Integrations</span>
          </TabsTrigger>
        </TabsList>

        {/* 1. Profile Tab */}
        <TabsContent value="profile">
          <div className="grid gap-6 md:grid-cols-2">
            <Card className="rounded-2xl border border-slate-200 bg-white shadow-2xs dark:bg-slate-900 dark:border-slate-800">
              <CardHeader>
                <div className="flex items-center justify-between">
                  <div>
                    <CardTitle className="text-slate-900 dark:text-slate-100">User Identity & Profile</CardTitle>
                    <CardDescription className="text-slate-500 dark:text-slate-400">
                      Authenticated user credentials, RBAC role, and account standing.
                    </CardDescription>
                  </div>
                  <div className="flex items-center gap-2">
                    {user?.email === 'demo@selfhealingrag.local' && (
                      <Badge variant="warning">DEMO</Badge>
                    )}
                    <Badge variant="default">{user?.role || 'USER'}</Badge>
                  </div>
                </div>
              </CardHeader>
              <CardContent className="space-y-4">
                <div className="flex items-center gap-4 pb-4 border-b border-slate-100 dark:border-slate-800">
                  <div className="flex h-14 w-14 items-center justify-center rounded-2xl bg-blue-600 text-white font-bold text-xl uppercase shadow-md shadow-blue-600/20">
                    {user?.name?.[0] || 'U'}
                  </div>
                  <div>
                    <h3 className="text-base font-semibold text-slate-900 dark:text-slate-100">
                      {user?.name || 'Authenticated User'}
                    </h3>
                    <p className="text-xs text-slate-500 dark:text-slate-400">{user?.email}</p>
                    <div className="flex items-center gap-2 mt-1">
                      <span className="inline-flex items-center gap-1 text-[11px] font-medium text-emerald-600 dark:text-emerald-400">
                        <CheckCircle2 className="h-3 w-3" />
                        Account Active
                      </span>
                      {user?.email === 'demo@selfhealingrag.local' && (
                        <span className="inline-flex items-center text-[11px] font-semibold text-amber-600 dark:text-amber-400">
                          · Development Demo Mode
                        </span>
                      )}
                    </div>
                  </div>
                </div>

                <div className="grid grid-cols-2 gap-4 text-xs">
                  <div>
                    <span className="text-slate-500 block">User Identifier</span>
                    <span className="font-mono text-slate-900 dark:text-slate-200 truncate block mt-0.5">
                      {user?.id || '—'}
                    </span>
                  </div>
                  <div>
                    <span className="text-slate-500 block">System Role</span>
                    <span className="font-semibold text-slate-900 dark:text-slate-200 block mt-0.5">
                      {user?.role} (Server Enforced)
                    </span>
                  </div>
                  <div>
                    <span className="text-slate-500 block">Account Created</span>
                    <span className="text-slate-700 dark:text-slate-300 block mt-0.5">
                      {user?.created_at ? new Date(user.created_at).toLocaleDateString() : '—'}
                    </span>
                  </div>
                  <div>
                    <span className="text-slate-500 block">Last Active Session</span>
                    <span className="text-slate-700 dark:text-slate-300 block mt-0.5">
                      {user?.last_login_at ? new Date(user.last_login_at).toLocaleTimeString() : 'Current'}
                    </span>
                  </div>
                </div>
              </CardContent>
            </Card>

            <Card className="rounded-2xl border border-slate-200 bg-white shadow-2xs dark:bg-slate-900 dark:border-slate-800">
              <CardHeader>
                <CardTitle className="text-slate-900 dark:text-slate-100">Access Privileges</CardTitle>
                <CardDescription className="text-slate-500 dark:text-slate-400">
                  Authorizations granted by your current role assignment.
                </CardDescription>
              </CardHeader>
              <CardContent className="space-y-3">
                <div className="p-3.5 rounded-xl border border-slate-100 bg-slate-50 dark:border-slate-800 dark:bg-slate-950/40 text-xs space-y-2">
                  <div className="flex items-center justify-between">
                    <span className="font-semibold text-slate-900 dark:text-slate-100">RAG Chat & Workflows</span>
                    <Badge variant="success">Granted</Badge>
                  </div>
                  <p className="text-slate-500 text-[11px]">
                    Authorized to submit queries, inspect retrieval traces, and execute agent flows.
                  </p>
                </div>

                <div className="p-3.5 rounded-xl border border-slate-100 bg-slate-50 dark:border-slate-800 dark:bg-slate-950/40 text-xs space-y-2">
                  <div className="flex items-center justify-between">
                    <span className="font-semibold text-slate-900 dark:text-slate-100">Knowledge Base Ingestion</span>
                    <Badge variant="success">Granted</Badge>
                  </div>
                  <p className="text-slate-500 text-[11px]">
                    Authorized to view workspace document catalogs and semantic indexes.
                  </p>
                </div>

                <div className="p-3.5 rounded-xl border border-slate-100 bg-slate-50 dark:border-slate-800 dark:bg-slate-950/40 text-xs space-y-2">
                  <div className="flex items-center justify-between">
                    <span className="font-semibold text-slate-900 dark:text-slate-100">Admin User Management</span>
                    {user?.role === 'ADMIN' ? (
                      <Badge variant="success">Administrator Only</Badge>
                    ) : (
                      <Badge variant="outline">Requires ADMIN</Badge>
                    )}
                  </div>
                  <p className="text-slate-500 text-[11px]">
                    {user?.role === 'ADMIN'
                      ? 'You hold administrative privileges to inspect user rosters.'
                      : 'Server-side RBAC enforces ADMIN privileges for user management endpoints.'}
                  </p>
                </div>
              </CardContent>
            </Card>
          </div>
        </TabsContent>

        {/* 2. Security & Sessions Tab */}
        <TabsContent value="security">
          <div className="grid gap-6 lg:grid-cols-2">
            {/* Change Password Form */}
            <Card className="rounded-2xl border border-slate-200 bg-white shadow-2xs dark:bg-slate-900 dark:border-slate-800">
              <CardHeader>
                <div className="flex items-center gap-2">
                  <KeyRound className="h-5 w-5 text-blue-600 dark:text-blue-400" />
                  <CardTitle className="text-slate-900 dark:text-slate-100">Change Account Password</CardTitle>
                </div>
                <CardDescription className="text-slate-500 dark:text-slate-400">
                  Update your authentication credential. Password must be at least 8 characters.
                </CardDescription>
              </CardHeader>
              <CardContent>
                {passwordError && (
                  <div className="mb-4 flex items-start gap-2.5 rounded-xl border border-rose-200 bg-rose-50 p-3 text-xs text-rose-800 dark:border-rose-900/50 dark:bg-rose-950/30 dark:text-rose-300">
                    <AlertCircle className="h-4 w-4 shrink-0 text-rose-600 dark:text-rose-400 mt-0.5" />
                    <span>{passwordError}</span>
                  </div>
                )}

                <form onSubmit={handleChangePassword} className="space-y-4">
                  <div className="space-y-1.5">
                    <label className="text-xs font-semibold text-slate-700 dark:text-slate-300">
                      Current Password
                    </label>
                    <Input
                      type="password"
                      value={currentPassword}
                      onChange={(e) => setCurrentPassword(e.target.value)}
                      placeholder="••••••••••••"
                      className="bg-white border-slate-200 text-slate-900 dark:bg-slate-800 dark:border-slate-700 dark:text-slate-100"
                      required
                    />
                  </div>

                  <div className="space-y-1.5">
                    <label className="text-xs font-semibold text-slate-700 dark:text-slate-300">
                      New Password
                    </label>
                    <Input
                      type="password"
                      value={newPassword}
                      onChange={(e) => setNewPassword(e.target.value)}
                      placeholder="At least 8 characters with letter & number"
                      className="bg-white border-slate-200 text-slate-900 dark:bg-slate-800 dark:border-slate-700 dark:text-slate-100"
                      required
                    />
                  </div>

                  <div className="space-y-1.5">
                    <label className="text-xs font-semibold text-slate-700 dark:text-slate-300">
                      Confirm New Password
                    </label>
                    <Input
                      type="password"
                      value={confirmNewPassword}
                      onChange={(e) => setConfirmNewPassword(e.target.value)}
                      placeholder="Re-enter new password"
                      className="bg-white border-slate-200 text-slate-900 dark:bg-slate-800 dark:border-slate-700 dark:text-slate-100"
                      required
                    />
                  </div>

                  <Button
                    type="submit"
                    size="sm"
                    loading={changePasswordMutation.isPending}
                    className="gap-2"
                  >
                    <Lock className="h-3.5 w-3.5" />
                    <span>Update Password</span>
                  </Button>
                </form>
              </CardContent>
            </Card>

            {/* Active Sessions List */}
            <Card className="rounded-2xl border border-slate-200 bg-white shadow-2xs dark:bg-slate-900 dark:border-slate-800">
              <CardHeader>
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <Laptop className="h-5 w-5 text-blue-600 dark:text-blue-400" />
                    <CardTitle className="text-slate-900 dark:text-slate-100">Active User Sessions</CardTitle>
                  </div>
                  <Button
                    variant="outline"
                    size="xs"
                    onClick={handleLogoutAll}
                    className="text-rose-600 hover:text-rose-700 dark:text-rose-400 gap-1.5"
                  >
                    <LogOut className="h-3 w-3" />
                    <span>Revoke All Everywhere</span>
                  </Button>
                </div>
                <CardDescription className="text-slate-500 dark:text-slate-400">
                  Devices authenticated with rotated refresh token families.
                </CardDescription>
              </CardHeader>
              <CardContent className="space-y-3">
                {sessionsLoading ? (
                  <div className="py-8 text-center text-xs text-slate-500">
                    Loading active sessions from security repository...
                  </div>
                ) : !sessions || sessions.length === 0 ? (
                  <div className="py-8 text-center text-xs text-slate-500">
                    No active remote sessions found.
                  </div>
                ) : (
                  sessions.map((sess) => (
                    <div
                      key={sess.id}
                      className="flex items-center justify-between p-3 rounded-xl border border-slate-100 bg-slate-50/70 text-xs dark:border-slate-800 dark:bg-slate-950/40"
                    >
                      <div className="space-y-1">
                        <div className="flex items-center gap-2">
                          <span className="font-semibold text-slate-900 dark:text-slate-100">
                            {sess.user_agent ? sess.user_agent.split(' ')[0] : 'Web Client'}
                          </span>
                          {sess.is_current ? (
                            <Badge variant="success">Current Session</Badge>
                          ) : (
                            <Badge variant="outline">Remote Device</Badge>
                          )}
                        </div>
                        <p className="text-[11px] text-slate-500 font-mono">
                          IP: {sess.ip_address || '127.0.0.1'} · Created:{' '}
                          {new Date(sess.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                        </p>
                      </div>

                      {!sess.is_current && (
                        <Button
                          variant="ghost"
                          size="xs"
                          onClick={() => handleRevokeSession(sess.id)}
                          loading={revokeSessionMutation.isPending}
                          className="text-rose-600 hover:bg-rose-50 dark:hover:bg-rose-950/40"
                          title="Revoke this session"
                        >
                          <Trash2 className="h-3.5 w-3.5" />
                        </Button>
                      )}
                    </div>
                  ))
                )}

                <div className="mt-4 p-3 rounded-xl border border-slate-100 bg-blue-50/40 text-[11px] text-slate-600 dark:border-slate-800 dark:bg-blue-950/20 dark:text-slate-400">
                  <div className="font-semibold text-blue-700 dark:text-blue-300 mb-1">
                    Token Rotation & Family Reuse Protection
                  </div>
                  Each session is tracked by a cryptographic token family. If an expired or intercepted refresh token is reused, all related sessions are automatically revoked server-side.
                </div>
              </CardContent>
            </Card>
          </div>
        </TabsContent>

        {/* 3. General Workspace Tab */}
        <TabsContent value="general">
          <Card className="rounded-2xl border border-slate-200 bg-white shadow-2xs dark:bg-slate-900 dark:border-slate-800">
            <CardHeader>
              <CardTitle className="text-slate-900 dark:text-slate-100">General Workspace Settings</CardTitle>
              <CardDescription className="text-slate-500 dark:text-slate-400">
                Configure tenant display name, visual interface theme, and default preferences.
              </CardDescription>
            </CardHeader>
            <CardContent>
              <form onSubmit={handleSaveGeneral} className="space-y-4 max-w-lg">
                <div className="space-y-1.5">
                  <label className="text-xs font-semibold text-slate-700 dark:text-slate-300">
                    Workspace Name
                  </label>
                  <Input
                    value={workspaceName}
                    onChange={(e) => setWorkspaceName(e.target.value)}
                    className="bg-white border-slate-200 text-slate-900 dark:bg-slate-800 dark:border-slate-700 dark:text-slate-100"
                  />
                </div>

                <div className="space-y-1.5">
                  <label className="text-xs font-semibold text-slate-700 dark:text-slate-300">
                    Interface Theme
                  </label>
                  <div className="flex gap-2">
                    <Button
                      type="button"
                      variant={theme === 'light' ? 'default' : 'outline'}
                      size="sm"
                      onClick={() => setTheme('light')}
                      className="gap-2"
                    >
                      <Sun className="h-4 w-4" />
                      <span>Light</span>
                    </Button>
                    <Button
                      type="button"
                      variant={theme === 'dark' ? 'default' : 'outline'}
                      size="sm"
                      onClick={() => setTheme('dark')}
                      className="gap-2"
                    >
                      <Moon className="h-4 w-4" />
                      <span>Dark</span>
                    </Button>
                  </div>
                </div>

                <Button type="submit" size="sm" className="gap-2">
                  <Save className="h-4 w-4" />
                  <span>Save Workspace</span>
                </Button>
              </form>
            </CardContent>
          </Card>
        </TabsContent>

        {/* 4. AI Models Tab */}
        <TabsContent value="models">
          <Card className="rounded-2xl border border-slate-200 bg-white shadow-2xs dark:bg-slate-900 dark:border-slate-800">
            <CardHeader>
              <CardTitle className="text-slate-900 dark:text-slate-100">LLM Generation Parameters</CardTitle>
              <CardDescription className="text-slate-500 dark:text-slate-400">
                Model configurations for upcoming generation and agent workflows.
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-4 max-w-lg">
              <div className="space-y-1.5">
                <label className="text-xs font-semibold text-slate-700 dark:text-slate-300">
                  Primary LLM Provider
                </label>
                <Select
                  value={llmProvider}
                  onChange={(e) => setLlmProvider(e.target.value)}
                >
                  <option value="openai">OpenAI (GPT-4o, GPT-4o-mini)</option>
                  <option value="groq">Groq (Llama 3.3 / Llama 3.1)</option>
                  <option value="anthropic">Anthropic (Claude 3.5 Sonnet)</option>
                </Select>
              </div>

              <div className="space-y-1.5">
                <label className="text-xs font-semibold text-slate-700 dark:text-slate-300">
                  Generation Model
                </label>
                <Input
                  value={llmModel}
                  onChange={(e) => setLlmModel(e.target.value)}
                  className="font-mono text-xs"
                />
              </div>

              <div className="space-y-1.5">
                <div className="flex justify-between text-xs">
                  <span className="font-semibold text-slate-700 dark:text-slate-300">Temperature</span>
                  <span className="font-mono text-blue-600 dark:text-blue-400 font-bold">{temperature}</span>
                </div>
                <input
                  type="range"
                  min="0.0"
                  max="1.0"
                  step="0.05"
                  value={temperature}
                  onChange={(e) => setTemperature(parseFloat(e.target.value))}
                  className="w-full accent-blue-600 cursor-pointer"
                />
              </div>

              <div className="space-y-1.5">
                <label className="text-xs font-semibold text-slate-700 dark:text-slate-300">
                  Max Generation Tokens
                </label>
                <Input
                  type="number"
                  value={maxTokens}
                  onChange={(e) => setMaxTokens(parseInt(e.target.value, 10))}
                  className="font-mono text-xs"
                />
              </div>

              <Button
                size="sm"
                onClick={() => toast.success('Model parameters updated')}
                className="gap-2"
              >
                <Save className="h-4 w-4" />
                <span>Save Model Preferences</span>
              </Button>
            </CardContent>
          </Card>
        </TabsContent>

        {/* 5. Retrieval Tab */}
        <TabsContent value="retrieval">
          <Card className="rounded-2xl border border-slate-200 bg-white shadow-2xs dark:bg-slate-900 dark:border-slate-800">
            <CardHeader>
              <div className="flex items-center justify-between">
                <div>
                  <CardTitle className="text-slate-900 dark:text-slate-100">Retrieval & Indexing Policies</CardTitle>
                  <CardDescription className="text-slate-500 dark:text-slate-400">
                    Configure hybrid fusion weights, chunk sizes, and reranking thresholds.
                  </CardDescription>
                </div>
                <Badge variant="purple">Hybrid RRF Architecture</Badge>
              </div>
            </CardHeader>
            <CardContent className="space-y-4 max-w-lg">
              <div className="space-y-1.5">
                <div className="flex justify-between text-xs">
                  <span className="font-semibold text-slate-700 dark:text-slate-300">
                    Hybrid Search Alpha Weight
                  </span>
                  <span className="font-mono text-blue-600 dark:text-blue-400 font-bold">{hybridAlpha}</span>
                </div>
                <input
                  type="range"
                  min="0.0"
                  max="1.0"
                  step="0.05"
                  value={hybridAlpha}
                  onChange={(e) => setHybridAlpha(parseFloat(e.target.value))}
                  className="w-full accent-blue-600 cursor-pointer"
                />
                <div className="flex justify-between text-[10px] text-slate-500">
                  <span>BM25 Lexical (0.0)</span>
                  <span>pgvector Semantic (1.0)</span>
                </div>
              </div>

              <div className="space-y-1.5">
                <div className="flex justify-between text-xs">
                  <span className="font-semibold text-slate-700 dark:text-slate-300">
                    Similarity Score Cutoff Threshold
                  </span>
                  <span className="font-mono text-blue-600 dark:text-blue-400 font-bold">{similarityThreshold}</span>
                </div>
                <input
                  type="range"
                  min="0.4"
                  max="0.95"
                  step="0.05"
                  value={similarityThreshold}
                  onChange={(e) => setSimilarityThreshold(parseFloat(e.target.value))}
                  className="w-full accent-blue-600 cursor-pointer"
                />
              </div>

              <div className="space-y-1.5">
                <label className="text-xs font-semibold text-slate-700 dark:text-slate-300">
                  Default Retrieval Candidates (Top-K)
                </label>
                <Input
                  type="number"
                  value={topK}
                  onChange={(e) => setTopK(parseInt(e.target.value, 10))}
                  className="font-mono text-xs"
                />
              </div>

              <Button
                size="sm"
                onClick={() => toast.success('Retrieval parameters saved')}
                className="gap-2"
              >
                <Save className="h-4 w-4" />
                <span>Save Retrieval Policies</span>
              </Button>
            </CardContent>
          </Card>
        </TabsContent>

        {/* 6. Integrations Tab */}
        <TabsContent value="integrations">
          <div className="grid gap-4 sm:grid-cols-2">
            {[
              { name: 'PostgreSQL & pgvector', status: 'Active connection verified', phase: 'Database & Vector' },
              { name: 'Redis Cache & Session Store', status: 'Running on localhost:6379', phase: 'In-Memory Cache' },
              { name: 'Argon2id & JWT Auth', status: 'Real Authentication Active', phase: 'Auth & Security' },
              { name: 'Amazon S3 / MinIO Object Storage', status: 'Ready in docker-compose', phase: 'Object Storage' },
            ].map((integ, i) => (
              <Card key={i} className="p-4 rounded-xl border border-slate-200 bg-white shadow-2xs dark:bg-slate-900 dark:border-slate-800">
                <div className="flex items-center justify-between mb-2">
                  <span className="text-xs font-semibold text-slate-900 dark:text-slate-100">{integ.name}</span>
                  <Badge variant="outline" size="sm" className="font-mono">{integ.phase}</Badge>
                </div>
                <p className="text-[11px] text-slate-500">{integ.status}</p>
              </Card>
            ))}
          </div>
        </TabsContent>
      </Tabs>
    </div>
  );
}
