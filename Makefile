.PHONY: install lint format typecheck test check run connect appliances programs status appliance-status

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

connect:
	uv run hcs connect

appliances:
	uv run hcs appliances

programs:
	uv run hcs programs

status:
	uv run hcs status

appliance-status:
	uv run hcs appliance-status
