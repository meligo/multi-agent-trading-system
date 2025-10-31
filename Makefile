.PHONY: help install install-dev test lint format clean run docs

help:
	@echo "Available commands:"
	@echo "  install      Install production dependencies"
	@echo "  install-dev  Install development dependencies"
	@echo "  test         Run tests"
	@echo "  lint         Run linters"
	@echo "  format       Format code"
	@echo "  clean        Clean build artifacts"
	@echo "  run          Run the system"
	@echo "  docs         Build documentation"

install:
	pip install -r requirements/prod.txt

install-dev:
	pip install -r requirements/dev.txt
	pre-commit install

test:
	pytest tests/ -v --cov=src --cov-report=term-missing

lint:
	flake8 src tests
	mypy src
	pylint src

format:
	black src tests
	isort src tests

clean:
	find . -type d -name "__pycache__" -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete
	find . -type f -name "*.pyo" -delete
	find . -type d -name "*.egg-info" -exec rm -rf {} +
	find . -type d -name ".pytest_cache" -exec rm -rf {} +
	find . -type d -name ".mypy_cache" -exec rm -rf {} +
	rm -rf build/ dist/ .coverage htmlcov/

run:
	python -m src.main NVDA

docs:
	cd docs && make html
