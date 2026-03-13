SHELL := /bin/bash

BACKEND_DIR  := backend
FRONTEND_DIR := frontend
VENV         := $(BACKEND_DIR)/venv
PYTHON       := $(VENV)/bin/python
PIP          := $(VENV)/bin/pip
UVICORN      := $(VENV)/bin/uvicorn
ALEMBIC      := $(VENV)/bin/alembic
NODE         := $(shell command -v node 2>/dev/null || echo "$(HOME)/.nvm/versions/node/v22.17.1/bin/node")
NPM          := $(shell command -v npm  2>/dev/null || echo "$(HOME)/.nvm/versions/node/v22.17.1/bin/npm")
VITE         := $(FRONTEND_DIR)/node_modules/.bin/vite

BACKEND_LOG  := /tmp/qlgen-backend.log
FRONTEND_LOG := /tmp/qlgen-frontend.log

.PHONY: help install install-backend install-frontend \
        db-start db-stop db-wait \
        migrate migrate-create \
        dev dev-backend dev-frontend \
        stop stop-backend stop-frontend \
        status logs logs-backend logs-frontend \
        clean clean-backend clean-frontend \
        seed-admin

# ─── Default ───────────────────────────────────────────────────────────────────

help:
	@echo ""
	@echo "  qlGen — Makefile Commands"
	@echo ""
	@echo "  Setup"
	@echo "    make install           Install all dependencies (backend + frontend)"
	@echo "    make install-backend   Create venv and install Python packages"
	@echo "    make install-frontend  Run npm install"
	@echo ""
	@echo "  Database"
	@echo "    make db-start          Start PostgreSQL via Docker Compose"
	@echo "    make db-stop           Stop PostgreSQL container"
	@echo "    make migrate           Apply pending Alembic migrations"
	@echo "    make migrate-create    Create a new migration (set MSG=<name>)"
	@echo ""
	@echo "  Run"
	@echo "    make dev               Start both backend and frontend"
	@echo "    make dev-backend       Start backend only  (http://localhost:8000)"
	@echo "    make dev-frontend      Start frontend only (http://localhost:3000)"
	@echo ""
	@echo "  Stop"
	@echo "    make stop              Stop both backend and frontend"
	@echo "    make stop-backend      Stop backend only"
	@echo "    make stop-frontend     Stop frontend only"
	@echo ""
	@echo "  Logs"
	@echo "    make logs              Tail both logs"
	@echo "    make logs-backend      Tail backend log"
	@echo "    make logs-frontend     Tail frontend log"
	@echo ""
	@echo "  Misc"
	@echo "    make status            Show running services"
	@echo "    make clean             Remove venv and node_modules"
	@echo ""

# ─── Install ───────────────────────────────────────────────────────────────────

install: install-backend install-frontend

install-backend:
	@echo "→ Setting up Python virtual environment..."
	python3 -m venv $(VENV)
	$(PIP) install --upgrade pip -q
	$(PIP) install -r $(BACKEND_DIR)/requirements.txt -q
	@echo "✓ Backend dependencies installed"

install-frontend:
	@echo "→ Installing frontend dependencies..."
	cd $(FRONTEND_DIR) && $(NPM) install
	@echo "✓ Frontend dependencies installed"

# ─── Database ──────────────────────────────────────────────────────────────────

db-start:
	@echo "→ Starting PostgreSQL..."
	docker compose up -d db
	@$(MAKE) db-wait

db-stop:
	@echo "→ Stopping PostgreSQL..."
	docker compose stop db

db-wait:
	@echo "→ Waiting for PostgreSQL to be ready..."
	@for i in $$(seq 1 20); do \
		pg_isready -h localhost -p 5432 -U qlgen -q && echo "✓ PostgreSQL ready" && exit 0; \
		sleep 1; \
	done; \
	echo "✗ PostgreSQL did not become ready in time" && exit 1

migrate:
	@echo "→ Running database migrations..."
	cd $(BACKEND_DIR) && $(ALEMBIC) upgrade head
	@echo "✓ Migrations applied"

migrate-create:
	@if [ -z "$(MSG)" ]; then echo "✗ Usage: make migrate-create MSG=\"description\""; exit 1; fi
	cd $(BACKEND_DIR) && $(ALEMBIC) revision --autogenerate -m "$(MSG)"

# ─── Dev ───────────────────────────────────────────────────────────────────────

dev: dev-backend dev-frontend
	@echo ""
	@echo "✓ qlGen is running"
	@echo "  Frontend → http://localhost:3000"
	@echo "  Backend  → http://localhost:8000"
	@echo "  API docs → http://localhost:8000/docs"
	@echo ""
	@echo "  Run 'make logs'   to tail logs"
	@echo "  Run 'make stop'   to stop all services"

dev-backend:
	@echo "→ Starting backend..."
	@mkdir -p $$(dirname $(BACKEND_LOG))
	@cp -n qlgen/.env $(BACKEND_DIR)/.env 2>/dev/null || cp -n .env $(BACKEND_DIR)/.env 2>/dev/null || true
	@nohup $(UVICORN) app.main:app \
		--host 0.0.0.0 \
		--port 8000 \
		--reload \
		--app-dir $(BACKEND_DIR) \
		> $(BACKEND_LOG) 2>&1 & echo $$! > /tmp/qlgen-backend.pid
	@for i in $$(seq 1 15); do \
		curl -sf http://localhost:8000/api/v1/health > /dev/null 2>&1 && \
		echo "✓ Backend running on http://localhost:8000 (pid=$$(cat /tmp/qlgen-backend.pid))" && exit 0; \
		sleep 1; \
	done; \
	echo "✗ Backend failed to start — check $(BACKEND_LOG)" && exit 1

dev-frontend:
	@echo "→ Starting frontend..."
	@mkdir -p $$(dirname $(FRONTEND_LOG))
	@cd $(FRONTEND_DIR) && nohup $(NODE) node_modules/.bin/vite \
		> $(FRONTEND_LOG) 2>&1 & echo $$! > /tmp/qlgen-frontend.pid
	@for i in $$(seq 1 20); do \
		curl -sf http://localhost:3000 > /dev/null 2>&1 && \
		echo "✓ Frontend running on http://localhost:3000 (pid=$$(cat /tmp/qlgen-frontend.pid))" && exit 0; \
		sleep 1; \
	done; \
	echo "✗ Frontend failed to start — check $(FRONTEND_LOG)" && exit 1

# ─── Stop ──────────────────────────────────────────────────────────────────────

stop: stop-backend stop-frontend

stop-backend:
	@if [ -f /tmp/qlgen-backend.pid ]; then \
		kill $$(cat /tmp/qlgen-backend.pid) 2>/dev/null; \
		rm -f /tmp/qlgen-backend.pid; \
	fi
	@kill $$(lsof -ti:8000) 2>/dev/null || true
	@echo "✓ Backend stopped"

stop-frontend:
	@if [ -f /tmp/qlgen-frontend.pid ]; then \
		kill $$(cat /tmp/qlgen-frontend.pid) 2>/dev/null; \
		rm -f /tmp/qlgen-frontend.pid; \
	fi
	@kill $$(lsof -ti:3000) 2>/dev/null || true
	@echo "✓ Frontend stopped"

# ─── Logs ──────────────────────────────────────────────────────────────────────

logs:
	@tail -f $(BACKEND_LOG) $(FRONTEND_LOG)

logs-backend:
	@tail -f $(BACKEND_LOG)

logs-frontend:
	@tail -f $(FRONTEND_LOG)

# ─── Status ────────────────────────────────────────────────────────────────────

status:
	@echo ""
	@echo "  Service Status"
	@echo "  ─────────────────────────────"
	@pg_isready -h localhost -p 5432 -U qlgen -q 2>/dev/null \
		&& echo "  PostgreSQL  ✓  localhost:5432" \
		|| echo "  PostgreSQL  ✗  not running"
	@curl -sf http://localhost:8000/api/v1/health > /dev/null 2>&1 \
		&& echo "  Backend     ✓  http://localhost:8000" \
		|| echo "  Backend     ✗  not running"
	@curl -sf http://localhost:3000 > /dev/null 2>&1 \
		&& echo "  Frontend    ✓  http://localhost:3000" \
		|| echo "  Frontend    ✗  not running"
	@echo ""

# ─── Clean ─────────────────────────────────────────────────────────────────────

seed-admin:
	@if [ -z "$(EMAIL)" ]; then echo "✗ Usage: make seed-admin EMAIL=user@example.com"; exit 1; fi
	cd $(BACKEND_DIR) && $(PYTHON) -m app.scripts.seed_admin $(EMAIL)

clean: clean-backend clean-frontend

clean-backend:
	@echo "→ Removing backend venv..."
	rm -rf $(VENV)
	find $(BACKEND_DIR) -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	@echo "✓ Backend cleaned"

clean-frontend:
	@echo "→ Removing frontend node_modules..."
	rm -rf $(FRONTEND_DIR)/node_modules $(FRONTEND_DIR)/dist
	@echo "✓ Frontend cleaned"
