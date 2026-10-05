SHELL := /bin/sh
-include .env
WEB_PORT ?= 8000
MAILPIT_PORT ?= 8025
.DEFAULT_GOAL := help

COMPOSE      := docker compose
COMPOSE_PROD := docker compose -f docker-compose.prod.yml
WEB          := $(COMPOSE) exec web
MANAGE       := $(WEB) python manage.py

.PHONY: help env build up down restart logs ps shell bash dbshell migrate makemigrations \
        superuser seed test lint format check collectstatic clean \
        prod-build prod-up prod-down prod-logs prod-migrate prod-seed prod-superuser

help: ## Show this help
	@grep -hE '^[a-zA-Z_-]+:.*?## ' Makefile | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[33m%-16s\033[0m %s\n", $$1, $$2}'

env: ## Create .env from .env.example (if missing)
	@test -f .env || cp .env.example .env && echo ".env ready"

# ── Development ──────────────────────────────────────────
build: env ## Build dev images
	$(COMPOSE) build

up: env ## Start dev stack (site + Mailpit)
	$(COMPOSE) up -d --build
	@echo "Site:    http://localhost:$(WEB_PORT)"
	@echo "Console: http://localhost:$(WEB_PORT)/console/"
	@echo "Mailpit: http://localhost:$(MAILPIT_PORT)"

down: ## Stop dev stack
	$(COMPOSE) down

restart: ## Restart the web container
	$(COMPOSE) restart web

logs: ## Tail web logs
	$(COMPOSE) logs -f web

ps: ## List containers
	$(COMPOSE) ps

shell: ## Django shell
	$(MANAGE) shell

bash: ## Shell inside the web container
	$(WEB) sh

dbshell: ## psql into the database
	$(COMPOSE) exec db sh -c 'psql -U $$POSTGRES_USER -d $$POSTGRES_DB'

migrate: ## Apply migrations
	$(MANAGE) migrate

makemigrations: ## Create migrations
	$(MANAGE) makemigrations

superuser: ## Create a Django superuser
	$(MANAGE) createsuperuser

seed: ## Load demo content, pricing tiers and the initial admin account
	$(MANAGE) seed

test: ## Run the test suite
	$(WEB) sh -c 'cd /app && pytest -q'

lint: ## Lint with ruff
	$(WEB) sh -c 'cd /app && ruff check src'

format: ## Auto-format with ruff
	$(WEB) sh -c 'cd /app && ruff format src && ruff check --fix src'

check: ## Django deploy checks against prod settings
	$(WEB) sh -c 'DJANGO_SETTINGS_MODULE=config.settings.prod DEBUG=False python manage.py check --deploy'

collectstatic: ## Collect static files
	$(MANAGE) collectstatic --noinput

clean: ## Stop dev stack and DELETE its volumes (database, uploads)
	$(COMPOSE) down -v

# ── Production ───────────────────────────────────────────
prod-build: ## Build production images
	$(COMPOSE_PROD) build

prod-up: ## Start production stack (Caddy + HTTPS)
	$(COMPOSE_PROD) up -d --build
	@echo ""
	@echo "Site:    https://$(DOMAIN)"
	@echo "Console: https://$(DOMAIN)/console/"
	@echo "First run on a fresh database? 'make prod-seed' creates the pricing and the admin login."

prod-down: ## Stop production stack
	$(COMPOSE_PROD) down

prod-logs: ## Tail production logs
	$(COMPOSE_PROD) logs -f web caddy

prod-migrate: ## Apply migrations in production
	$(COMPOSE_PROD) exec web python manage.py migrate

prod-seed: ## Seed pricing + admin in production (no demo orders)
	$(COMPOSE_PROD) exec web python manage.py seed --no-demo

prod-superuser: ## Create a superuser in production
	$(COMPOSE_PROD) exec web python manage.py createsuperuser
