# OpsKnowledge Agent Lite — common Docker Compose / dev commands
#
# Usage:
#   make up        # build & start the full stack (postgres + ollama + backend + frontend)
#   make down      # stop containers, keep volumes (data persists)
#   make restart   # restart services without rebuild
#   make build     # rebuild backend / frontend images
#   make logs      # tail logs for all services
#   make logs-backend / logs-frontend / logs-postgres / logs-ollama
#   make pull-ollama # pull the default local LLM model into ollama_data
#   make ps        # list running containers
#   make health    # curl backend /health
#   make test      # run backend test suite inside the backend container
#   make test-local # run backend tests via local .venv (no Docker)
#   make psql      # open psql shell inside the postgres container
#   make clean     # stop containers AND drop the named volumes (DESTRUCTIVE — wipes data)

COMPOSE ?= docker compose

.PHONY: up down restart build logs logs-backend logs-frontend logs-postgres logs-ollama \
        ps health test test-local psql pull-ollama clean help

help:
	@grep -E '^[a-zA-Z_-]+:.*?##' $(MAKEFILE_LIST) || \
	awk 'BEGIN{print "Targets:"} /^[a-zA-Z_-]+:/{sub(/:.*/,""); print "  " $$0}' $(MAKEFILE_LIST) | sort -u

up:
	@test -f .env || (echo "❌ .env 不存在，請先執行: cp .env.example .env" && exit 1)
	$(COMPOSE) up --build -d
	@echo ""
	@echo "✅ Stack started. URLs:"
	@echo "   Frontend  http://localhost:8501"
	@echo "   Backend   http://localhost:8000/docs"
	@echo "   Health    http://localhost:8000/health"
	@echo "   Next      make pull-ollama"

down:
	$(COMPOSE) down

restart:
	$(COMPOSE) restart

build:
	$(COMPOSE) build

logs:
	$(COMPOSE) logs -f --tail=200

logs-backend:
	$(COMPOSE) logs -f --tail=200 backend

logs-frontend:
	$(COMPOSE) logs -f --tail=200 frontend

logs-postgres:
	$(COMPOSE) logs -f --tail=200 postgres

logs-ollama:
	$(COMPOSE) logs -f --tail=200 ollama

ps:
	$(COMPOSE) ps

health:
	@curl -fsS http://localhost:8000/health | python3 -m json.tool || echo "❌ backend 不可用"

test:
	$(COMPOSE) exec backend sh -c "PYTHONPATH=. pytest tests/ -q"

test-local:
	cd backend && . .venv/bin/activate && PYTHONPATH=. pytest tests/ -q

psql:
	$(COMPOSE) exec postgres psql -U $${POSTGRES_USER:-opsuser} -d $${POSTGRES_DB:-opsknowledge}

pull-ollama:
	$(COMPOSE) up -d ollama
	$(COMPOSE) exec ollama ollama pull $${OLLAMA_MODEL:-qwen2.5:7b-instruct}

# DESTRUCTIVE: 停掉 stack 並刪除 named volumes (postgres 資料與 ollama 模型會消失)
# 已在指令前印警語；如需自動化，可使用 `yes | make clean`。
clean:
	@echo "⚠️  將刪除 postgres_data / ollama_data volumes — 所有資料與已下載模型會永久消失。"
	@read -p "確定要繼續嗎？(y/N): " ans && [ "$$ans" = "y" ] || (echo "已取消"; exit 1)
	$(COMPOSE) down -v
