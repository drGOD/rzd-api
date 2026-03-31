.PHONY: install test run docker-build docker-up docker-down

install:
	pip install -e ".[dev]"

test:
	pytest tests/ -v

run:
	pip install -e ".[mcp]"
	rzd-mcp-server

docker-build:
	docker build -t rzd-api .

docker-up:
	docker compose up -d

docker-down:
	docker compose down
