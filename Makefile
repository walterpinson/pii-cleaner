.PHONY: install test lint format clean

install:
uv sync

test:
uv run pytest tests/ -v --tb=short

test-cov:
uv run pytest tests/ -v --tb=short --cov=pii_cleaner --cov-report=term-missing

lint:
uv run ruff check pii_cleaner/ tests/

format:
uv run ruff format pii_cleaner/ tests/

clean:
find . -type d -name __pycache__ -exec rm -rf {} +
find . -type d -name .pytest_cache -exec rm -rf {} +
find . -name "*.pyc" -delete
rm -rf dist/ build/ *.egg-info
