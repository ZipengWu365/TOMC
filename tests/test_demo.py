"""Exercise all bundled scenarios and the actual Gradio callbacks offline."""

import json
from importlib.resources import files

import pytest

from tomc import STRATEGIES, compile_memory


@pytest.mark.parametrize("name", ["preferences", "constraints", "agent", "evidence", "snapshot"])
def test_all_synthetic_examples(name):
    example = json.loads(files("tomc").joinpath(f"data/{name}.json").read_text(encoding="utf-8"))
    for strategy in STRATEGIES:
        result = compile_memory(example["messages"], example["query"], example["budget"], strategy)
        assert result.compiled_memory
        if strategy != "raw":
            assert result.stats.budget_compliant


def test_demo_callbacks_and_layout(monkeypatch):
    pytest.importorskip("gradio")
    from demo.app import SCENARIOS, compare_view, compile_view, create_demo, load_example

    sample = load_example(SCENARIOS[0]["title"])
    result = compile_view(*sample[:4], 1.0)
    assert len(result) == 8 and result[-1]["ledger"]
    left, right, table = compare_view(sample[0], sample[1], 160, "raw", "tomc", 1)
    assert len(left) > len(right) and len(table) == 2
    assert table[0][5] is False and table[1][5] is True
    demo = create_demo()
    assert demo.analytics_enabled is False


def test_offline_shell_removes_only_optional_external_resources():
    pytest.importorskip("gradio")
    from demo.offline import offline_shell

    shell = b'<script src="https://cdnjs.cloudflare.com/ajax/libs/iframe-resizer/4.3.1/iframeResizer.contentWindow.min.js" async></script><script src="/assets/app.js"></script><link rel="preconnect" href="https://fonts.gstatic.com" crossorigin="anonymous"/>'
    assert offline_shell(shell) == b'<script src="/assets/app.js"></script>'


def test_tour_renders_real_snapshot_sources_and_explicit_overhead():
    from demo.tour import render_tour

    html = render_tour("State updates & snapshots")
    assert "backup_drink" in html and "decaf tea" in html
    assert "u0 · message 1, line 1" in html and "u2 · message 2, line 1" in html
    assert "drink = tea" in html and "backup_drink copies drink" in html
    assert "31 → 36" in html and "expands this tiny example" in html
    assert "reader answers" in html


def test_tour_escapes_compiler_values_and_marks_omitted_rows(monkeypatch):
    from dataclasses import replace

    from demo import tour

    result = compile_memory("drink = tea", "current drink", 0, "tomc")
    result.ledger[0] = replace(result.ledger[0], value='<img src=x onerror="bad()">')
    monkeypatch.setattr(tour, "compile_memory", lambda *a, **kw: result)
    html = tour.render_tour("State updates & snapshots")
    assert "<img" not in html and "&lt;img" in html
    assert "Budget omitted · audit only" in html
    assert "In memory · sources" not in html
