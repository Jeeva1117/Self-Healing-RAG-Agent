.PHONY: help install test lint format dev-backend dev-frontend migrate docker-up docker-down

help:
	@echo "Available commands:"
	@echo "  make install        Install backend and frontend dependencies"
	@echo "  make test           Run all automated tests"
	@echo "  make test-backend   Run backend pytest suite"
	@echo "  make lint           Run backend and frontend linters"
	@echo "  make format         Auto-format codebases"
	@echo "  make migrate        Run Alembic database migrations"
	@echo "  make dev-backend    Start FastAPI backend development server"
	@echo "  make dev-frontend   Start Vite React development server"
	@echo "  make docker-up      Start PostgreSQL, Redis, Backend, and Frontend in Docker"
	@echo "  make docker-down    Stop Docker Compose containers"

install:
	pip install -r backend/requirements-dev.txt
	cd frontend && npm install

test: test-backend test-frontend

test-backend:
	pytest -o pythonpath=backend backend/tests

test-frontend:
	cd frontend && npm run test && npm run build

lint: lint-backend lint-frontend

lint-backend:
	ruff check backend/app backend/tests

lint-frontend:
	cd frontend && npx oxlint

format:
	ruff format backend/app backend/tests
	ruff check --fix backend/app backend/tests

migrate:
	cd backend && alembic upgrade head

dev-backend:
	cd backend && uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

dev-frontend:
	cd frontend && npm run dev

docker-up:
	docker compose up -d

docker-down:
	docker compose down
