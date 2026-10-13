# Self-Healing RAG Agent — Frontend Application

Modern React 19 and TypeScript single-page application for the **Self-Healing RAG Agent** enterprise knowledge and adaptive retrieval platform.

---

## Technology Stack

- **Framework**: [React 19](https://react.dev/) + [Vite](https://vitejs.dev/)
- **Language**: [TypeScript](https://www.typescriptlang.org/) (Strict mode, ES2023)
- **Styling**: [Tailwind CSS v4](https://tailwindcss.com/)
- **Routing**: [React Router v7](https://reactrouter.com/)
- **Data Fetching & Cache**: [TanStack Query v5](https://tanstack.com/query)
- **Interactive Topologies**: [@xyflow/react (React Flow)](https://reactflow.dev/) for LangGraph multi-agent flow visualization
- **Telemetry Charts**: [Recharts](https://recharts.org/)
- **Form Validation**: [React Hook Form](https://react-hook-form.com/) + [Zod](https://zod.dev/)
- **Iconography**: [Lucide React](https://lucide.dev/)
- **Testing**: [Vitest](https://vitest.dev/)

---

## Directory Structure

```text
frontend/
├── public/                # Static assets (favicons, SVG icons)
├── src/
│   ├── assets/            # Bundled images and vectors
│   ├── components/        # Reusable UI component design system
│   │   ├── auth/          # ProtectedRoute, RoleGuard
│   │   ├── common/        # ArchitectureFlow, CommandPalette, StatusBadge
│   │   ├── knowledge-base/# HealthExplorer, RepairCenter, VersioningView, Duplicates
│   │   ├── layout/        # AppLayout, Header, Sidebar, MobileNav
│   │   └── ui/            # Button, Card, Badge, Modal, Tabs, Drawer, MetricCard
│   ├── config/            # Runtime environment configuration
│   ├── constants/         # Navigation routes and platform constants
│   ├── context/           # AuthContext, ThemeContext, ToastContext
│   ├── hooks/             # Custom React hooks (useAuth, useHealth, useKnowledgeBase)
│   ├── pages/             # Application route views (Chat, KnowledgeBase, DataSources, etc.)
│   ├── routes/            # Route declarations and guarded paths
│   ├── services/          # Typed API client services
│   ├── tests/             # Vitest unit and integration test suites
│   ├── types/             # Domain TypeScript interfaces and API schemas
│   ├── App.tsx            # Root component with providers
│   ├── index.css          # Core CSS tokens and Tailwind entry
│   └── main.tsx           # Application entry point
├── package.json           # Dependencies and scripts
├── tsconfig.app.json      # App TypeScript configuration
├── tsconfig.json          # Root TS project configuration
└── vite.config.ts         # Vite bundler configuration
```

---

## Available Scripts

Run from `frontend/` directory (or use workspace root proxy scripts):

```bash
# Start Vite development server on http://localhost:5173
npm run dev

# Run Vitest unit tests
npm run test

# Type-check and build production bundle (outputs to dist/)
npm run build

# Run linter
npm run lint

# Preview production build locally
npm run preview
```

---

## Environment Configuration

Frontend environment variables are read at build time by Vite:

| Variable | Default | Description |
| :--- | :--- | :--- |
| `VITE_API_URL` | `http://localhost:8000/api/v1` | Backend FastAPI base URL |
| `VITE_DEMO_LOGIN_ENABLED` | `true` (dev) / `false` (prod) | Displays quick-login button for local testing |
