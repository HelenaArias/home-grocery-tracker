test:
	docker compose run --rm --no-deps api python -m pytest tests/ -v

test-watch:
	docker compose run --rm --no-deps api python -m pytest tests/ -v --tb=short -x
