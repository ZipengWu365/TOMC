"""Exercise all bundled scenarios and the actual Gradio callbacks offline."""

import json
import re
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
    assert "\u2212" in result[1] and "≈ $" in result[5] and "estimate" in result[5]
    # No price: no money shown at all, never a fake $0.
    assert "$" not in compile_view(*sample[:4], 0)[5]
    assert "≈ $" in compile_view(*sample[:4], 1.0, lang="zh")[5]
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
    from demo.tour import LIMIT_CASE, limits_note, render_tour

    html = render_tour(LIMIT_CASE)
    assert "backup_drink" in html and "decaf tea" in html
    assert "u0 · message 1, line 1" in html and "u2 · message 2, line 1" in html
    assert "drink = tea" in html and "backup_drink copies drink" in html
    assert "31 → 36" in html and "expands this tiny example" in html
    assert "reader answers" in html
    # The growing case is framed as a limit, with the same live numbers.
    assert "very short chats don't need compression" in limits_note("en")
    assert "31 变成 36" in limits_note("zh") and "不需要压缩" in limits_note("zh")


def test_tour_cases_show_compression_first():
    from demo.tour import CASES, LIMIT_CASE, render_tour

    assert LIMIT_CASE not in CASES
    for case in CASES:
        for lang in ("en", "zh"):
            html = render_tour(case, lang)
            assert "\u2212" in html and "grew" not in html
    assert "662 → 58" in render_tour(next(iter(CASES)), "zh")


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


def test_page_defaults_to_chinese_and_footer_reads_the_package_version():
    pytest.importorskip("gradio")
    import tomc
    from demo.app import LANG_CHOICES, create_demo, footer_html, language_from_request

    assert next(iter(LANG_CHOICES.values())) == "zh"
    choice, zh, en = language_from_request(None)
    assert choice == "中文" and zh.visible is True and en.visible is False

    class Request:
        query_params = {"lang": "en"}

    choice, zh, en = language_from_request(Request())
    assert choice == "English" and zh.visible is False and en.visible is True
    for lang in ("zh", "en"):
        assert f"v{tomc.__version__}" in footer_html(lang)
        assert "v0.1" not in footer_html(lang)
    config = create_demo().get_config_file()
    radio = next(c for c in config["components"] if c["props"].get("elem_id") == "lang-switch")
    assert radio["props"]["value"] == "中文"
    html = json.dumps(config, ensure_ascii=False)
    assert "改过的事" in html and "When a fact changes" in html
    assert "TomC" not in html


def test_page_opens_on_a_live_result_with_a_minus_sign_and_estimate_label():
    pytest.importorskip("gradio")
    from demo.easy import first_result, prepare_view, quick_example

    history, task, prompt, status, *_, strip = first_result("zh")
    assert (history, task) == quick_example("120-day project chat", "zh")
    assert prompt and "framework = Litestar" in prompt
    assert status.count("少发") == 1 and "token（\u2212" in status and "估算" in status
    assert "第 234 行" in status and "第 188 行" in status
    # The first line is the reduction, never a plus sign for it.
    big = status.split('class="big"', 1)[1].split("</strong>", 1)[0]
    assert "+" not in big and "\u2212" in big

    # Same function, same budget: recomputing gives the same numbers (the time may differ).
    def numbers(text):
        return re.sub(r"不到 0\.01 秒|\d+\.\d+ 秒", "", text)

    assert numbers(prepare_view(history, task, "Small request", "zh")[1]) == numbers(status)
    # The side-by-side strip shows kept lines with their original line numbers.
    assert "<b>234</b>" in strip and "framework = Litestar" in strip and "行没带上" in strip
    en = first_result("en")
    assert "fewer tokens (\u2212" in en[3] and "estimate" in en[3]


def test_reduction_headline_signs():
    from demo.easy import input_reduction

    assert input_reduction(1000, 100, "zh") == "少发 900 token（\u221290%）"
    assert input_reduction(1000, 100) == "900 fewer tokens (\u221290%)"
    assert "+" not in input_reduction(1000, 999) and "\u22121%" in input_reduction(1000, 999)
    assert input_reduction(100, 130, "zh") == "上下文增加了 30 token（+30%）"
    assert input_reduction(100, 100, "zh") == "没有变化（0%）"


def test_source_strip_escapes_text_and_marks_multi_message_lines():
    from demo.easy import source_strip
    from tomc import prepare_context

    history = [
        {"role": "user", "content": "framework = Flask\n<b>note</b> " + "filler words " * 40},
        {"role": "assistant", "content": "ok " * 60},
        {"role": "user", "content": "framework = FastAPI"},
    ]
    result = prepare_context(history, "current framework?", 24).compilation
    strip = source_strip(history, result, "en")
    assert "<b>note</b>" not in strip
    assert "3:1" in strip and "FastAPI" in strip
