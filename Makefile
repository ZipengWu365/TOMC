PYTHON ?= python3
VENV = .venv
PY = $(VENV)/bin/python

.PHONY: install demo test lint reproduce-results build-docs security-scan manifest build launch-assets project-assets
install:
	@if command -v uv >/dev/null 2>&1; then \
		uv venv --allow-existing $(VENV) && uv pip install --python $(PY) -e '.[demo,dev,mcp]'; \
	else \
		$(PYTHON) -m venv $(VENV) && $(PY) -m pip install -e '.[demo,dev,mcp]'; \
	fi
demo:
	GRADIO_ANALYTICS_ENABLED=False $(PY) -m demo.app
test:
	$(PY) -m pytest -q
lint:
	$(VENV)/bin/ruff check .
	$(VENV)/bin/ruff format --check .
reproduce-results:
	$(PY) benchmarks/reproduce/current.py
	$(PY) benchmarks/reproduce/results.py
build-docs:
	$(VENV)/bin/mkdocs build --strict
security-scan:
	$(PY) scripts/security_scan.py
manifest:
	$(PY) scripts/release_manifest.py
build:
	$(PY) -m build
launch-assets:
	$(PY) scripts/launch_assets.py
project-assets:
	$(PY) scripts/project_figures.py
