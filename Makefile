COMPOSE := docker compose

.PHONY: up down logs lint migrate

up:
	$(COMPOSE) up -d --build

down:
	$(COMPOSE) down

logs:
	$(COMPOSE) logs -f --tail=100

lint:
	uv run ruff check .
	uv run ruff format --check .
	uv run mypy

migrate:
	$(COMPOSE) run --rm migrate
