"""A value changed later must not be presented as current: regressions from the v0.2.1 review.

Each history spreads a few key lines through routine filler notes, as a long working
history does. "Latest" checks require the newest value in the memory and no unflagged
STATE record that still asserts an older one.
"""

import sys
import unicodedata
from pathlib import Path

import pytest

from tomc import compile_memory, prepare_context
from tomc.input import parse_history
from tomc.ledger import normalize
from tomc.routing import task_route
from tomc.store import MemoryStore
from tomc.strategies.baselines import rank_bm25
from tomc.tokenization import RegexCounter

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "benchmarks" / "adaptive"))
from suite import two_hop_cases  # noqa: E402

TIGHT = 300
FILLER = [
    "Reviewed the onboarding copy for the landing page and fixed two typos.",
    "Discussed the sprint retro; people want shorter standups on Mondays.",
    "Logged a flaky screenshot test in the design system storybook.",
    "Someone asked about holiday coverage for the support rota next month.",
    "Benchmarked image thumbnails; the resize step dominates upload time.",
    "Talked through naming for the analytics events in the mobile app.",
    "Paired on a CSS grid layout bug in the settings page sidebar.",
    "Noted that the staging certificate renews automatically every quarter.",
]
FILLER_ZH = [
    "今天上午复盘了上周的迭代，大家觉得站会可以再短一点。",
    "设计同学更新了落地页的配色，按钮颜色改成了深蓝色。",
    "测试环境的证书每个季度会自动续期，不需要人工处理。",
    "讨论了移动端埋点事件的命名规范，暂时沿用旧的前缀。",
    "有人问下个月客服值班怎么排，先按原来的轮换表执行。",
    "图片缩略图压测结果显示，主要耗时在缩放这一步。",
]


def filler(n, zh=False):
    pool = FILLER_ZH if zh else FILLER
    return [f"{pool[i % len(pool)]} (note {i})" for i in range(n)]


def spread(key_lines, n=120, zh=False):
    """Key lines in order, evenly spaced through n filler lines."""
    out, step, k = [], max(1, n // (len(key_lines) + 1)), 0
    for i, line in enumerate(filler(n, zh)):
        out.append(line)
        if k < len(key_lines) and (i + 1) % step == 0:
            out.append(key_lines[k])
            k += 1
    return "\n".join(out + key_lines[k:])


def assert_latest(result, key, latest):
    memory = result.compiled_memory
    stale = [r for r in result.ledger if r.included and r.kind == "STATE" and r.key.lower() == key]
    assert all(latest in r.value for r in stale), stale
    assert latest in memory, memory[:400]


# ---- Values changed in plain words after a key = value line ----


@pytest.mark.parametrize(
    ("lines", "task", "key", "latest", "zh"),
    [
        (
            ["framework = FastAPI", "scratch that, keep Flask"],
            "current framework?",
            "framework",
            "Flask",
            False,
        ),
        (
            ["cache = redis", "We removed redis; there is no cache any more."],
            "What is the current cache?",
            "cache",
            "no cache",
            False,
        ),
        (
            ["db = postgres", "db 改成 mysql 了，postgres 不用了。"],
            "当前 db 是什么？",
            "db",
            "mysql",
            True,
        ),
        (
            ["framework = Flask", "我们决定改用 FastAPI 了"],
            "当前 framework 是什么？",
            "framework",
            "FastAPI",
            True,
        ),
        (
            ["db = postgres", "db = mysql", "Actually, undo the last change."],
            "What is the current db?",
            "db",
            "postgres",
            False,
        ),
        (
            ["framework = Flask", "Correction: we moved to FastAPI last week."],
            "What is the current framework?",
            "framework",
            "FastAPI",
            False,
        ),
    ],
)
def test_a_later_plain_language_change_flags_the_compiled_value(lines, task, key, latest, zh):
    result = compile_memory(spread(lines, zh=zh), task, TIGHT, "hybrid")
    assert_latest(result, key, latest)
    flagged = [r for r in result.ledger if r.included and r.kind == "STATE?"]
    assert flagged and flagged[0].key == key and "(later: u" in flagged[0].value
    # The doubtful value is followed by the line that put it in doubt.
    memory = result.compiled_memory.splitlines()
    row = next(i for i, line in enumerate(memory) if line.startswith("[STATE?]"))
    assert memory[row + 1].startswith(f"[RAW {flagged[0].sources[-1]}] ")
    assert "marked STATE?" in " ".join(result.warnings)


@pytest.mark.parametrize(
    "change",
    [
        "Morning sync: the nightly benchmark moved by 3 percent, probably noise.",
        "早会：夜间基准变化了 3%，大概是噪声。",
    ],
)
def test_an_amount_that_moved_does_not_put_an_asked_value_in_doubt(change):
    # "moved by 3 percent" is an amount, not a new value for the asked key.
    result = compile_memory(
        spread(["db = postgres", change]), "What is the current db?", TIGHT, "hybrid"
    )
    assert_latest(result, "db", "postgres")
    assert not [r for r in result.ledger if r.included and r.kind == "STATE?"]


def test_the_default_prepare_budget_flags_the_value_too():
    history = spread(["framework = FastAPI", "scratch that, keep Flask"])
    result = prepare_context(history, "What is the current framework?").compilation
    assert_latest(result, "framework", "Flask")


def test_unrelated_changes_do_not_flag_a_value():
    # "按钮颜色改成了深蓝色" changes a button colour, and "a rollback task" undoes nothing.
    result = compile_memory(
        spread(["数据库 = PostgreSQL", "数据库 = MySQL"], zh=True), "当前数据库是什么？", TIGHT
    )
    assert [(r.kind, r.key, r.value) for r in result.ledger] == [("STATE", "数据库", "MySQL")]
    notes = "framework = FastAPI\nWednesday: the team added a rollback task and postponed docs."
    result = compile_memory(notes, "What is the current framework?", 200, "tomc")
    assert [(r.kind, r.value) for r in result.ledger] == [("STATE", "FastAPI")]


def test_a_new_assignment_after_the_change_is_current_again():
    history = "\n".join(["db = postgres", "We switched db to mysql.", "db = sqlite"])
    result = compile_memory(history, "What is the current db?", 200, "tomc")
    assert [(r.kind, r.value) for r in result.ledger] == [("STATE", "sqlite")]


def test_an_edge_removed_in_prose_is_flagged():
    history = spread(
        [
            "alice -[owns]-> repo1",
            "Alice no longer owns repo1; it moved to bob.",
            "bob -[owns]-> repo1",
        ]
    )
    result = compile_memory(history, "relation: owns", TIGHT, "hybrid")
    rows = {r.key: r for r in result.ledger}
    assert rows["alice"].kind == "PATH?" and "(later: u" in rows["alice"].value
    assert rows["bob"].kind == "PATH"


# ---- Accepted state-line forms ----


@pytest.mark.parametrize(
    ("line", "expected"),
    [
        ("db: mysql", [("db", "mysql")]),
        ("- db = mysql", [("db", "mysql")]),
        ("* db = mysql", [("db", "mysql")]),
        ("1. db = mysql", [("db", "mysql")]),
        ("Update: framework = FastAPI", [("framework", "FastAPI")]),
        ("ok so db = mysql from now on", [("db", "mysql")]),
        ("Priya: db = mysql", [("db", "mysql")]),
        ("user: Update: db = mysql", [("db", "mysql")]),
        ("db = mysql; port = 3306", [("db", "mysql"), ("port", "3306")]),
        ("数据库＝MySQL", [("数据库", "MySQL")]),
        ("数据库：MySQL", [("数据库", "MySQL")]),
        ("数据库 = MySQL", [("数据库", "MySQL")]),
        ("timeout = 30 s", [("timeout", "30 s")]),
        ("x == y", []),
        ("a != b", []),
        ("I copy that", []),
        ("Alice takes notes", []),
        ("Alice: sounds good", []),
        ("user: hello there", []),
        ("张三：好的我知道了", []),
        ("Release date: March 3.", []),
        ("I might prefer tea someday, but I have not decided.", []),
    ],
)
def test_state_line_forms(line, expected):
    result = compile_memory(line, "current state", 200, "tomc")
    assert [(r.key, r.value) for r in result.ledger] == expected


def test_keys_ignore_case_and_show_the_latest_spelling():
    result = compile_memory("DB = postgres\ndb = mysql", "What is the current db?", 200, "tomc")
    assert [(r.key, r.value) for r in result.ledger] == [("db", "mysql")]
    copies = compile_memory("A = 3\nB copies a\nA = 8", "current state", 200, "tomc")
    assert {r.key: r.value for r in copies.ledger} == {"A": "8", "B": "3"}


def test_code_blocks_examples_and_document_metadata_set_no_state():
    fenced = "db = postgres\nExample config, NOT our setup:\n```python\ndb = 'sqlite'\n```"
    hypothetical = [
        {"role": "user", "content": "db = mysql"},
        {"role": "assistant", "content": "If you wanted Mongo you would write:\ndb = mongo"},
    ]
    for history, value in ((fenced, "postgres"), (hypothetical, "mysql")):
        result = compile_memory(history, "What is the current db?", 200, "tomc")
        assert [(r.key, r.value) for r in result.ledger] == [("db", value)]
    docs = "---\nproject: aurora\n---\n# Aurora\n---\nproject: basalt\n---\n# Basalt"
    assert compile_memory(docs, "current state", 200, "tomc").ledger == []


def test_the_asked_key_is_kept_among_many_others():
    history = "\n".join(
        [f"k{i:03d} = v{i}" for i in range(140)]
        + ["zeta_db = postgres", *filler(30), "zeta_db = mysql"]
    )
    result = compile_memory(history, "What is the current zeta_db?", 400, "hybrid")
    assert any(r.key == "zeta_db" and r.value == "mysql" and r.included for r in result.ledger)


# ---- Routing ----


@pytest.mark.parametrize(
    ("task", "route"),
    [
        ("Which account is linked to user Alice?", "relation"),
        ("Who is the account owner now?", "state"),
        ("What discount applies to the order?", "raw"),
        ("Which country hosts the server?", "raw"),
        ("How many concurrent workers do we run?", "count"),
        ("What is the install path?", "raw"),
        ("relation: assigned > owns", "relation"),
        ("path: assigned > owns", "relation"),
        ("What is the current db?", "state"),
        ("Count the word redis", "count"),
        ("数据库现在是哪个？", "state"),
        ("目前用的是哪个框架？", "state"),
        ("如今谁负责？", "state"),
        ("最后定的是哪个方案？", "state"),
        ("缓存出现了多少次？", "count"),
    ],
)
def test_routing_uses_whole_words_and_chinese_state_words(task, route):
    assert task_route(task).value == route


# ---- Recency ----


def test_a_tie_keeps_the_later_line_only_for_current_value_tasks():
    _, units = normalize("first unrelated note\nsecond unrelated note")
    later = rank_bm25(units, "rate limit", later_first=True)
    assert later[0].text == "second unrelated note"
    assert rank_bm25(units, "rate limit")[0].text == "first unrelated note"


@pytest.mark.parametrize(
    ("budget", "recalled"),
    [(4096, [1, 1, 1, 0, 0, 0, 0, 0, 0]), (None, [1, 1, 1, 0, 1, 1, 1, 0, 0])],
)
def test_filling_recalls_two_step_chains_as_v021_did(budget, recalled):
    # The second link shares no word with the task, so it survives only by position;
    # tasks that are not about a current value keep v0.2.1's earlier-line preference.
    got = []
    for case in two_hop_cases():
        memory = prepare_context(case.history, case.task, budget, adaptive=False)
        text = memory.compilation.compiled_memory
        got.append(int(all(all(t in text for t in fact) for fact in case.facts)))
    assert got == recalled


@pytest.mark.parametrize("adaptive", [None, False])
def test_the_latest_message_survives_the_default_budget(adaptive):
    chat = (
        [{"role": "user", "content": "Our API rate limit is 100 requests per minute."}]
        + [
            {"role": "assistant" if i % 2 else "user", "content": f}
            for i, f in enumerate(filler(150))
        ]
        + [{"role": "user", "content": "Ops raised it to 250/min today."}]
    )
    memory = prepare_context(chat, "What is the API rate limit?", adaptive=adaptive)
    assert "250" in memory.compilation.compiled_memory


@pytest.mark.parametrize(
    ("lines", "task", "latest"),
    [
        (
            ["framework = Flask", "Correction: we moved to FastAPI last week."],
            "What is the current framework?",
            "FastAPI",
        ),
        (
            ["The API rate limit is 100 requests per minute.", "Ops raised it to 250/min today."],
            "What is the API rate limit?",
            "250",
        ),
    ],
)
def test_adaptive_notes_keep_a_correction_that_shares_no_word_with_the_task(lines, task, latest):
    result = prepare_context(spread(lines), task).compilation
    assert latest in result.compiled_memory


def test_the_adaptive_floor_is_filled():
    history = "\n".join(filler(3000) + ["The API rate limit is 100 requests per minute."])
    result = prepare_context(history, "What is the API rate limit?", 8000).compilation
    assert result.diagnostics["adaptive"] == "shrunk"
    assert result.stats.output_tokens >= 0.25 * 8000 - 40


def test_recent_mentions_are_kept_when_older_ones_fill_the_budget():
    lines = [f"The rate limit discussion {i} covered the rate limit rate limit." for i in range(60)]
    history = "\n".join(lines + ["rate limit is 250 now"])
    result = compile_memory(history, "What is the rate limit?", 120, "rag")
    assert "rate limit is 250 now" in result.compiled_memory


# ---- Long paragraphs ----


def test_a_long_paragraph_is_split_into_sentences_with_line_provenance():
    paragraph = " ".join(f"Sentence {i} about the migration plan." for i in range(1500))
    paragraph += " Final decision: db = mysql."
    result = prepare_context(paragraph, "What is the final db decision?").compilation
    assert "mysql" in result.compiled_memory
    assert "[RAW u0." in result.compiled_memory
    assert [u.source_id for u in result.evidence] == ["u0"]
    assert result.evidence[0].text == paragraph
    assert result.diagnostics["split_lines"] == 1
    zh = "。".join(f"第{i}句讨论迁移计划" for i in range(1500)) + "。最终决定：数据库改用 MySQL。"
    assert "MySQL" in prepare_context(zh, "最终数据库用什么？").compilation.compiled_memory


def test_a_line_that_fits_is_never_split():
    result = compile_memory("db = mysql. port = 3306.", "current db", 200, "tomc_raw")
    assert "split_lines" not in result.diagnostics and "[RAW u0]" in result.compiled_memory


# ---- Counts ----


def test_counts_put_the_asked_term_first_and_count_chinese_terms():
    history = "\n".join(filler(400) + ["We picked Redis for the queue."] * 3)
    result = compile_memory(history, "How many times was Redis mentioned?", 600, "tomc")
    assert (result.ledger[0].key, result.ledger[0].value) == ("redis", "occ=3, support=3")
    assert result.ledger[0].included
    zh = "\n".join(filler(60, zh=True) + ["我们把缓存换成了 Redis。", "缓存命中率提升了。"])
    result = compile_memory(zh, "缓存出现了多少次？", 600, "tomc")
    assert (result.ledger[0].key, result.ledger[0].value) == ("缓存", "occ=2, support=2")
    absent = compile_memory("apple pear", "How many times was kafka mentioned?", 100, "tomc")
    assert (absent.ledger[0].key, absent.ledger[0].value) == ("kafka", "occ=0, support=0")


# ---- Input, tokens and notebook names ----


@pytest.mark.parametrize(
    "history",
    [
        '{"event": "deploy", "ok": true}\nAfter that we set db = mysql.\nThen lunch.',
        '{"a": 1}\n{"b": 2}',
    ],
)
def test_text_that_starts_with_a_json_line_is_plain_text(history):
    assert parse_history(history) == history
    assert prepare_context(history, "What is the current db?").compilation.compiled_memory


def test_a_broken_single_line_message_envelope_gets_a_clear_error():
    with pytest.raises(ValueError, match="not valid JSON"):
        parse_history('{"messages": [ broken')


def test_kana_and_hangul_count_per_character():
    counter = RegexCounter()
    assert counter.count("가" * 2000) == 2000
    assert counter.count("あ" * 2000) == 2000
    assert counter.count("カタカナ") == 4
    assert counter.count("你好，世界！") == 6
    assert counter.count("hello_world foo") == 2


def test_notebook_names_ignore_case_and_unicode_form(tmp_path):
    store = MemoryStore(tmp_path / "memory.sqlite3")
    assert store.remember("proj", "db = postgres")["name"] == "proj"
    assert store.remember("Proj ", "db = mysql")["name"] == "proj"
    store.remember(unicodedata.normalize("NFD", "café"), "a = 1")
    assert store.remember("café", "a = 2")["name"] == "café"
    assert sorted((n["name"], n["entries"]) for n in store.list()) == [("café", 2), ("proj", 2)]
    assert "mysql" in store.recall("PROJ", "What is the current db?", 200).prompt
    assert store.forget("PROJ")["deleted_entries"] == 2


def test_an_exact_legacy_name_wins_over_a_case_only_match(tmp_path):
    store = MemoryStore(tmp_path / "memory.sqlite3")
    with store._connection() as db:
        for name in ("work", "Work"):
            db.execute(
                "INSERT INTO entries(name,payload) VALUES (?,?)",
                (name, f'[{{"content": "owner = {name}", "role": "user"}}]'),
            )
    assert "owner = Work" in store.recall("Work", "current owner").prompt
    assert "owner = work" in store.recall("WORK", "current owner").prompt


def test_an_appended_labelled_update_is_current(tmp_path):
    store = MemoryStore(tmp_path / "memory.sqlite3")
    store.remember("p", "\n".join(filler(150) + ["framework = Flask"]))
    store.remember("p", "Update: framework = FastAPI")
    result = store.recall("p", "What is the current framework?", 200).compilation
    assert_latest(result, "framework", "FastAPI")
