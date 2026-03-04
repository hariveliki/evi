.PHONY: dev backend frontend test lint build install

install:
	uv sync
	cd frontend && npm install

backend:
	uv run uvicorn evi_weights.api.app:create_app --factory --reload --port 8000

frontend:
	cd frontend && npm run dev

dev:
	@echo "Starting backend and frontend..."
	$(MAKE) backend &
	$(MAKE) frontend

test:
	uv run pytest tests/ -v

lint:
	uv run ruff check evi_weights/ tests/

build:
	cd frontend && npm run build
