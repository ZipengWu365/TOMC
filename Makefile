PYTHON ?= python3
VENV = .venv
PY = $(VENV)/bin/python

.PHONY: install demo test lint reproduce reproduce-results build-docs security-scan manifest build launch-assets project-assets
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
# Offline checks of every published number that can be recomputed without a model or network.
# Check mode only: nothing tracked is rewritten, and any mismatch fails the target.
# Use `make reproduce PY=python` to run with the active Python instead of .venv.
reproduce:
	$(PY) benchmarks/reproduce/current.py --check
	$(PY) benchmarks/reproduce/results.py --check
	$(PY) scripts/make_beam_table.py --check
	$(PY) benchmarks/reproduce/beam10m_bootstrap.py --check
	$(PY) benchmarks/reproduce/synthetic_corpus.py
	$(PY) scripts/benchmarks/codex_retention_report.py --verify-published docs/validation_data/windows_codex_retention_20261005.json
	$(PY) benchmarks/stale/run.py --check
	$(PY) benchmarks/adaptive/run.py --check
	$(PY) benchmarks/reproduce/examples_check.py
	@echo "make reproduce: all offline checks passed."
# Rewrites the paper and historical reports and the historical plot from the saved aggregates.
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
