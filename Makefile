.PHONY: help install install-dev test lint format clean run

help:  ## Show this help message
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'

install:  ## Install package dependencies
	uv pip install -e .

install-dev:  ## Install package with development dependencies
	uv pip install -e ".[dev]"

test:  ## Run tests
	pytest -v

test-cov:  ## Run tests with coverage
	pytest --cov=stable_squirrel --cov-report=html --cov-report=term

lint:  ## Run linting checks
	ruff check src/ tests/
	mypy src/

format:  ## Format code
	black src/ tests/
	isort src/ tests/
	ruff check --fix src/ tests/

format-check:  ## Check code formatting without fixing
	black --check src/ tests/
	isort --check-only src/ tests/
	ruff check src/ tests/

clean:  ## Clean up build artifacts
	rm -rf build/
	rm -rf dist/
	rm -rf *.egg-info/
	rm -rf .pytest_cache/
	rm -rf htmlcov/
	find . -type d -name __pycache__ -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete

run:  ## Run the application
	python -m stable_squirrel

run-dev:  ## Run the application with development settings
	python -m stable_squirrel --log-level DEBUG

setup-pre-commit:  ## Setup pre-commit hooks
	pre-commit install

podman-build:  ## Build Podman image
	podman build -t stable-squirrel .

podman-run:  ## Run in Podman container
	podman run -p 8000:8000 stable-squirrel

podman-compose:  ## Run with podman-compose
	podman-compose up -d

install-systemd:  ## Install systemd service (requires sudo)
	sudo cp stable-squirrel.service /etc/systemd/system/
	sudo systemctl daemon-reload
	@echo "Service installed. Configure /etc/stable-squirrel/config.yaml then run:"
	@echo "  sudo systemctl enable --now stable-squirrel.service"

db-dev:  ## Start TimescaleDB for development
	podman run -d --name timescaledb-dev \
		-p 5432:5432 \
		-e POSTGRES_DB=stable_squirrel \
		-e POSTGRES_USER=stable_squirrel \
		-e POSTGRES_PASSWORD=changeme \
		-v timescaledb-data:/var/lib/postgresql/data \
		timescale/timescaledb:latest-pg15

db-stop:  ## Stop development database
	podman stop timescaledb-dev || true
	podman rm timescaledb-dev || true