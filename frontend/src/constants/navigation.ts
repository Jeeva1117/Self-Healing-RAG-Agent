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
  type LucideIcon,
} from 'lucide-react';

export interface NavItem {
  name: string;
  href: string;
  icon: LucideIcon;
  badge?: string;
  description: string;
  phase: string;
}

export const PRIMARY_NAV_ITEMS: NavItem[] = [
  {
    name: 'Chat',
    href: '/chat',
    icon: MessageSquare,
    description: 'AI Chat workspace with self-healing retrieval',
    phase: 'AI Chat',
  },
  {
    name: 'Knowledge Base',
    href: '/knowledge-base',
    icon: BookOpen,
    description: 'Document indexing and knowledge corpus',
    phase: 'Vector Corpus',
  },
  {
    name: 'Data Sources',
    href: '/data-sources',
    icon: Database,
    description: 'External data connectors and integrations',
    phase: 'Connectors',
  },
  {
    name: 'Agent Workflows',
    href: '/agent-workflows',
    icon: Network,
    description: 'LangGraph multi-agent cyclical topology',
    phase: 'Multi-Agent',
  },
  {
    name: 'Evaluation',
    href: '/evaluation',
    icon: CheckCircle2,
    description: 'Ragas precision, recall, and hallucination scores',
    phase: 'Benchmarks',
  },
  {
    name: 'Observability',
    href: '/observability',
    icon: Activity,
    description: 'OpenTelemetry traces and telemetry',
    phase: 'Telemetry',
  },
  {
    name: 'Settings',
    href: '/settings',
    icon: Settings,
    description: 'Platform hyperparameters and security settings',
    phase: 'Configuration',
  },
];

export interface NavSection {
  title: string;
  items: NavItem[];
}

export const NAVIGATION_SECTIONS: NavSection[] = [
  {
    title: 'Workspace',
    items: PRIMARY_NAV_ITEMS,
  },
  {
    title: 'System Topology',
    items: [
      {
        name: 'Dashboard',
        href: '/dashboard',
        icon: LayoutDashboard,
        description: 'System health, pipeline topologies, and infrastructure status',
        phase: 'System Topology',
      },
      {
        name: 'Search Playground',
        href: '/search',
        icon: Search,
        description: 'Hybrid retrieval inspector: BM25, vector distance, and rerank fusion',
        phase: 'Hybrid Search',
      },
    ],
  },
];

// Flat list for convenience
export const ALL_NAV_ITEMS: NavItem[] = [...PRIMARY_NAV_ITEMS, {
  name: 'Dashboard',
  href: '/dashboard',
  icon: LayoutDashboard,
  description: 'System health, pipeline topologies, and infrastructure status',
  phase: 'System Topology',
}, {
  name: 'Search Playground',
  href: '/search',
  icon: Search,
  description: 'Hybrid retrieval inspector: BM25, vector distance, and rerank fusion',
  phase: 'Hybrid Search',
}];
