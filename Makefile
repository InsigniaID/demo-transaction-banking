.PHONY: help install dev run build docker-build docker-run docker-stop clean migrate-up migrate-down migrate-create

# Default target
help:
	@echo "Available commands:"
	@echo "  install      - Install dependencies using uv"
	@echo "  dev          - Run application in development mode"
	@echo "  run          - Run application in production mode"
	@echo "  build        - Build Docker image"
	@echo "  docker-run   - Run application using docker-compose"
	@echo "  docker-stop  - Stop docker-compose services"
	@echo "  migrate-up   - Run database migrations"
	@echo "  migrate-down - Rollback last migration"
	@echo "  migrate-create - Create new migration (use: make migrate-create MSG='description')"
	@echo "  clean        - Clean up cache and temporary files"
	@echo "  help         - Show this help message"

# Install dependencies
install:
	@echo "Installing dependencies with uv..."
	uv sync

# Run in development mode with auto-reload
dev:
	@echo "Starting development server..."
	uv run uvicorn app.main:app --host 0.0.0.0 --port 8919 --reload

# Run in production mode
run:
	@echo "Starting production server..."
	uv run uvicorn app.main:app --host 0.0.0.0 --port 8919

# Build Docker image
build:
	@echo "Building Docker image..."
	docker build -t banking-demo:1.0.0 .

# Run with docker-compose
docker-run:
	@echo "Starting application with docker-compose..."
	docker-compose up -d

# Stop docker-compose services
docker-stop:
	@echo "Stopping docker-compose services..."
	docker-compose down

# Database migration commands
migrate-up:
	@echo "Running database migrations..."
	uv run alembic upgrade head

migrate-down:
	@echo "Rolling back last migration..."
	uv run alembic downgrade -1

migrate-create:
	@echo "Creating new migration: $(MSG)"
	uv run alembic revision --autogenerate -m "$(MSG)"

# Clean up
clean:
	@echo "Cleaning up..."
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete 2>/dev/null || true
	find . -type d -name ".pytest_cache" -exec rm -rf {} + 2>/dev/null || true