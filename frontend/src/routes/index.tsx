import { lazy, Suspense } from 'react';
import { createBrowserRouter, Navigate } from 'react-router-dom';
import { AppLayout } from '@/components/layout/AppLayout';
import { SkeletonCard } from '@/components/ui/skeleton';
import { ProtectedRoute } from '@/components/auth/ProtectedRoute';
import { LoginPage } from '@/pages/auth/LoginPage';
import { RegisterPage } from '@/pages/auth/RegisterPage';
import { ForgotPasswordPage } from '@/pages/auth/ForgotPasswordPage';
import { ResetPasswordPage } from '@/pages/auth/ResetPasswordPage';

// Lazy-loaded routes for code splitting
const DashboardPage = lazy(() => import('@/pages/DashboardPage').then((m) => ({ default: m.DashboardPage })));
const ChatPage = lazy(() => import('@/pages/ChatPage').then((m) => ({ default: m.ChatPage })));
const KnowledgeBasePage = lazy(() => import('@/pages/KnowledgeBasePage').then((m) => ({ default: m.KnowledgeBasePage })));
const DataSourcesPage = lazy(() => import('@/pages/DataSourcesPage').then((m) => ({ default: m.DataSourcesPage })));
const SearchPlaygroundPage = lazy(() => import('@/pages/SearchPlaygroundPage').then((m) => ({ default: m.SearchPlaygroundPage })));
const AgentWorkflowsPage = lazy(() => import('@/pages/AgentWorkflowsPage').then((m) => ({ default: m.AgentWorkflowsPage })));
const EvaluationPage = lazy(() => import('@/pages/EvaluationPage').then((m) => ({ default: m.EvaluationPage })));
const ObservabilityPage = lazy(() => import('@/pages/ObservabilityPage').then((m) => ({ default: m.ObservabilityPage })));
const SettingsPage = lazy(() => import('@/pages/SettingsPage').then((m) => ({ default: m.SettingsPage })));
const NotFoundPage = lazy(() => import('@/pages/NotFoundPage').then((m) => ({ default: m.NotFoundPage })));

function PageSuspenseWrapper({ children }: { children: React.ReactNode }) {
  return (
    <Suspense
      fallback={
        <div className="space-y-4 animate-in fade-in-50">
          <div className="h-8 w-48 bg-slate-800/60 rounded-md shimmer-mask" />
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
            <SkeletonCard />
            <SkeletonCard />
            <SkeletonCard />
            <SkeletonCard />
          </div>
        </div>
      }
    >
      {children}
    </Suspense>
  );
}

export const router = createBrowserRouter([
  // Public Authentication Routes
  {
    path: '/login',
    element: <LoginPage />,
  },
  {
    path: '/register',
    element: <RegisterPage />,
  },
  {
    path: '/forgot-password',
    element: <ForgotPasswordPage />,
  },
  {
    path: '/reset-password',
    element: <ResetPasswordPage />,
  },

  // Protected Application Routes
  {
    path: '/',
    element: (
      <ProtectedRoute>
        <AppLayout />
      </ProtectedRoute>
    ),
    children: [
      {
        index: true,
        element: <Navigate to="/chat" replace />,
      },
      {
        path: 'dashboard',
        element: <PageSuspenseWrapper><DashboardPage /></PageSuspenseWrapper>,
      },
      {
        path: 'chat',
        element: <PageSuspenseWrapper><ChatPage /></PageSuspenseWrapper>,
      },
      {
        path: 'knowledge-base',
        element: <PageSuspenseWrapper><KnowledgeBasePage /></PageSuspenseWrapper>,
      },
      {
        path: 'data-sources',
        element: <PageSuspenseWrapper><DataSourcesPage /></PageSuspenseWrapper>,
      },
      {
        path: 'search',
        element: <PageSuspenseWrapper><SearchPlaygroundPage /></PageSuspenseWrapper>,
      },
      {
        path: 'agent-workflows',
        element: <PageSuspenseWrapper><AgentWorkflowsPage /></PageSuspenseWrapper>,
      },
      {
        path: 'evaluation',
        element: <PageSuspenseWrapper><EvaluationPage /></PageSuspenseWrapper>,
      },
      {
        path: 'observability',
        element: <PageSuspenseWrapper><ObservabilityPage /></PageSuspenseWrapper>,
      },
      {
        path: 'settings',
        element: <PageSuspenseWrapper><SettingsPage /></PageSuspenseWrapper>,
      },
      {
        path: 'settings/security',
        element: <PageSuspenseWrapper><SettingsPage defaultTab="security" /></PageSuspenseWrapper>,
      },
      {
        path: '*',
        element: <PageSuspenseWrapper><NotFoundPage /></PageSuspenseWrapper>,
      },
    ],
  },
]);
