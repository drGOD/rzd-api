.PHONY: install test coverage lint typecheck check build run docker-build docker-up docker-down

install:
	python -m pip install -e ".[dev]"

test:
	python -m pytest tests/ -m "not integration" -q

coverage:
	python -m pytest tests/ -m "not integration" --cov --cov-report=term-missing

lint:
	ruff check .
	ruff format --check .

typecheck:
	mypy

check: lint typecheck coverage build

build:
	python -m build
	twine check dist/*

run:
	rzd-mcp-server

docker-build:
	docker build -t rzd-api:3.0.0 .

docker-up:
	docker compose up -d

docker-down:
	docker compose down
