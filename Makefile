.PHONY: test install run

install:
	uv sync

test:
	.venv/bin/pytest tests/ -v

run:
	.venv/bin/swarm-refactor
