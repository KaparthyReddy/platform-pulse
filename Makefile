.PHONY: install seed dashboard bot mcp test lint

install:
	pip install -r requirements.txt
	pip install -e .

seed:
	python -m pulse.simulator

dashboard:
	streamlit run src/pulse/dashboard.py

bot:
	python -m pulse.slack_bot

mcp:
	python -m pulse.mcp_server

test:
	pytest

lint:
	ruff check src tests
