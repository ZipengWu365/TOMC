"""AI amnesia stories, rewritten as synthetic histories: the latest value must come back.

Each ``examples/amnesia/<id>.txt`` holds ``# field: value`` headers, a ``---`` line,
then the history. See examples/amnesia/README.md for the format and credit rules.
"""

from pathlib import Path

import pytest

from tomc import prepare_context

FOLDER = Path(__file__).resolve().parents[1] / "examples" / "amnesia"
STATUSES = ("用户自述，未复现 / reported, not reproduced", "已复现（附命令） / reproduced")
REQUIRED = ("id", "title", "status", "credit", "task", "key", "latest", "budget")


def load(path):
    head, history = path.read_text(encoding="utf-8").split("\n---\n", 1)
    fields = {}
    for line in head.splitlines():
        name, _, value = line.removeprefix("# ").partition(":")
        fields[name.strip()] = value.strip()
    fields["stale"] = [v.strip() for v in fields.get("stale", "").split(",") if v.strip()]
    return fields, history


CASES = sorted(FOLDER.glob("*.txt"))


def test_there_is_at_least_one_case():
    assert CASES


@pytest.mark.parametrize("path", CASES, ids=lambda path: path.stem)
def test_case_header_is_complete(path):
    fields, history = load(path)
    assert all(fields.get(name) for name in REQUIRED), fields
    assert fields["id"] == path.stem
    assert fields["status"] in STATUSES
    if fields["status"].startswith("已复现"):
        assert fields.get("command"), "a reproduced case names the command that reproduces it"
    assert history.strip()


@pytest.mark.parametrize("path", CASES, ids=lambda path: path.stem)
def test_latest_value_comes_back_under_a_tight_budget(path):
    fields, history = load(path)
    result = prepare_context(history, fields["task"], int(fields["budget"])).compilation
    # The budget is tight: the history really had to be compressed.
    assert result.stats.output_tokens < result.stats.input_tokens / 2
    states = [
        row
        for row in result.ledger
        if row.included and row.kind == "STATE" and row.key.lower() == fields["key"].lower()
    ]
    assert states, result.compiled_memory[:400]
    assert all(fields["latest"] in row.value for row in states), states
    for old in fields["stale"]:
        assert not any(old in row.value for row in states), (old, states)


@pytest.mark.parametrize(
    "form", [".github/DISCUSSION_TEMPLATE/ai-amnesia.yml", ".github/ISSUE_TEMPLATE/ai_amnesia.yml"]
)
def test_story_forms_require_the_privacy_checkbox(form):
    yaml = pytest.importorskip("yaml")
    body = yaml.safe_load((FOLDER.parents[1] / form).read_text(encoding="utf-8"))["body"]
    ids = [item.get("id") for item in body if item["type"] != "markdown"]
    assert len(ids) == len(set(ids))
    assert {"assistant", "length", "fact", "changes", "answer", "tomc", "credit"} <= set(ids)
    privacy = next(item for item in body if item.get("id") == "privacy")
    first = privacy["attributes"]["options"][0]
    assert first["label"] == "我已删掉私人内容 / I removed private content" and first["required"]
