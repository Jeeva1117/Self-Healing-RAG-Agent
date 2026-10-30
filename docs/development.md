# Development Guide — Self-Healing RAG Agent

## 1. Prerequisites

- Python 3.11+ (Python 3.13 supported)
- Node.js 20+ (Node.js 24 installed)
- npm or pnpm
- Docker & Docker Compose (optional for local containerized deployment)
- PostgreSQL 16+ & Redis 7+

## 2. Local Setup Workflow

### Step 1: Clone and Inspect
```bash
git clone <repo-url>
cd "Self-Healing RAG Agent"
```

### Step 2: Configure Environment Variables
```bash
cp .env.example .env
# Review and adapt .env if your PostgreSQL or Redis credentials differ
```

### Step 3: Install Backend Virtual Environment
```bash
python -m venv backend/.venv
# Windows PowerShell
.\backend\.venv\Scripts\Activate.ps1
pip install -r backend/requirements-dev.txt
```

### Step 4: Install Frontend Dependencies
```bash
cd frontend
npm install
cd ..
```

### Step 5: Start Services Locally
**Terminal 1 — Backend API Server:**
```powershell
.\scripts\dev_backend.ps1
# Or: cd backend && uvicorn app.main:app --reload --port 8000
```

**Terminal 2 — Frontend Dev Server:**
```powershell
.\scripts\dev_frontend.ps1
# Or: cd frontend && npm run dev
```

### Step 6: Docker Compose Alternative
```bash
docker compose up -d
```

## 3. Running Automated Tests

```powershell
# Run both backend tests & frontend production typecheck (321 total tests)
.\scripts\run_tests.ps1

# Backend only (pytest: 275 tests passed, 1 skipped)
backend\.venv\Scripts\pytest -o pythonpath=backend backend\tests

# Frontend unit tests (Vitest: 46 tests passed)
cd frontend && npm run test

# Frontend production typecheck & optimized chunk build
cd frontend && npm run build
```

## 4. Code Formatting & Linting

```powershell
# Backend linting & syntax check (Ruff)
backend\.venv\Scripts\ruff check backend\app backend\tests --config pyproject.toml

# Backend auto-formatting
backend\.venv\Scripts\ruff format backend\app backend\tests

# Frontend linting (Oxlint)
cd frontend && npx oxlint
```
