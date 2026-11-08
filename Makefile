.PHONY: install seed dashboard mcp test lint

install:
	pip install -r requirements.txt
	pip install -e .

seed:
	python -m pulse.simulator

dashboard:
	streamlit run src/pulse/dashboard.py

mcp:
	python -m pulse.mcp_server

test:
	pytest

lint:
	ruff check src tests
