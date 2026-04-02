.PHONY: install lint format typecheck test check run

install:
	uv sync --all-extras

lint:
	uv run ruff check src tests

format:
	uv run ruff format src tests

typecheck:
	uv run ty check src

test:
	uv run pytest

check: format lint typecheck test

run:
	uv run hcs run
