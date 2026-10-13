# Contributing Guidelines

Thank you for your interest in contributing to **Self-Healing RAG Agent**! This guide outlines how to set up the development environment, run tests, and submit high-quality pull requests.

---

## 1. Development Prerequisites

- **Python**: 3.11 or higher
- **Node.js**: 20.x or higher (npm 10+)
- **PostgreSQL**: 16+ with `pgvector` extension
- **Redis** (optional): 7+ (fallback supported when disabled)

---

## 2. Setting Up the Local Workspace

```bash
# 1. Clone repository
git clone https://github.com/your-username/self-healing-rag-agent.git
cd self-healing-rag-agent

# 2. Configure environment
cp .env.example .env

# 3. Setup Python virtual environment
python -m venv backend/.venv
# Windows PowerShell:
.\backend\.venv\Scripts\pip install -r backend\requirements-dev.txt
# Linux/macOS:
source backend/.venv/bin/activate && pip install -r backend/requirements-dev.txt

# 4. Install Frontend dependencies
cd frontend && npm install && cd ..

# 5. Apply database migrations
backend/.venv/Scripts/alembic.exe -c alembic.ini upgrade head
```

---

## 3. Running Locally

Open two terminals:

**Terminal 1 — Backend:**
```powershell
backend\.venv\Scripts\uvicorn.exe app.main:app --reload --host 127.0.0.1 --port 8000
```

**Terminal 2 — Frontend:**
```powershell
npm run dev
```

---

## 4. Verification Checklist Before Submitting PRs

Always run the full test suites before creating a pull request:

```powershell
# Backend lint check (must have 0 errors)
backend\.venv\Scripts\ruff.exe check backend\app backend\tests

# Backend unit and integration tests (270+ tests must pass)
backend\.venv\Scripts\pytest.exe -o pythonpath=backend backend\tests

# Frontend unit tests
npm run test

# Frontend type check & production build (0 TypeScript errors)
npm run build
```

---

## 5. Coding Standards

- **Python**: Enforce PEP 8 conventions via Ruff. Use type hints for all public functions and models. Never commit hardcoded secrets or API keys.
- **TypeScript**: Strict type checking enabled (`tsc -b`). Do not use `@ts-ignore` or `any` unless strictly justified.
- **Commits**: Use Conventional Commits (`feat:`, `fix:`, `docs:`, `test:`, `refactor:`).
