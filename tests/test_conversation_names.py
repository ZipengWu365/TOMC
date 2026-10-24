import json
import sqlite3
from contextlib import closing

from tomc.conversation_names import claude_names, clean, codex_names, folder, resolve
from tomc.conversations import conversation_key, group_conversations

NAMED = "01a167c3-0000-7000-8000-000000000001"
INDEXED = "01a167c4-0000-7000-8000-000000000002"
UNNAMED = "01a167c5-0000-7000-8000-000000000003"
SUBAGENT = "01a167c8-0000-7000-8000-000000000004"
CLAUDE = "1fb18c0f-79a9-449b-b4ce-26836448d1dc"


def codex_home(tmp_path):
    home = tmp_path / "codex"
    home.mkdir()
    # An older state database must lose to the newest numbered one.
    sqlite3.connect(home / "state_4.sqlite").close()
    with closing(sqlite3.connect(home / "state_5.sqlite")) as db, db:
        db.execute(
            "CREATE TABLE threads (id TEXT PRIMARY KEY, name TEXT, title TEXT, cwd TEXT, "
            "agent_nickname TEXT, source TEXT)"
        )
        db.execute(
            "CREATE TABLE thread_spawn_edges (parent_thread_id TEXT, child_thread_id TEXT, status TEXT)"
        )
        db.executemany(
            "INSERT INTO threads VALUES (?,?,?,?,?,?)",
            [
                (
                    NAMED,
                    "Fix the  cat\nstage",
                    "first message A",
                    r"C:\work\TOMC-memory-branding",
                    None,
                    "user",
                ),
                (INDEXED, None, "first message B", "/home/me/publicity/", None, "user"),
                (UNNAMED, "", "  Review the gateway patch  ", None, None, "user"),
                (
                    SUBAGENT,
                    None,
                    "spawn prompt",
                    r"C:\work\TOMC-memory-branding",
                    "Ada",
                    "subagent",
                ),
            ],
        )
        db.execute("INSERT INTO thread_spawn_edges VALUES (?,?,?)", (NAMED, SUBAGENT, "done"))
    (home / "session_index.jsonl").write_text(
        "\n".join(
            json.dumps({"id": INDEXED, "thread_name": name, "updated_at": "x"})
            for name in ("Old name", "Publicity plan")
        )
        + "\nnot json\n",
        encoding="utf-8",
    )
    return home


def test_codex_names_follow_the_hosts_own_precedence(tmp_path):
    names = codex_names([NAMED, INDEXED, UNNAMED, SUBAGENT, "missing"], codex_home(tmp_path))
    assert names[NAMED] == {
        "title": "Fix the cat stage",
        "folder": "TOMC-memory-branding",
        "agent": None,
        "subagent": False,
    }
    assert names[INDEXED]["title"] == "Publicity plan"  # the latest rename wins
    assert names[INDEXED]["folder"] == "publicity"
    assert names[UNNAMED]["title"] == "Review the gateway patch"  # what Codex shows
    # A sub-agent thread is listed under its parent's name.
    assert names[SUBAGENT]["title"] == "Fix the cat stage"
    assert names[SUBAGENT]["agent"] == "Ada" and names[SUBAGENT]["subagent"]
    assert "missing" not in names


def test_codex_index_still_names_threads_without_a_state_database(tmp_path):
    home = codex_home(tmp_path)
    for path in home.glob("state_*.sqlite"):
        path.unlink()
    assert codex_names([INDEXED, NAMED], home) == {
        INDEXED: {"title": "Publicity plan", "folder": None, "agent": None, "subagent": False}
    }
    assert codex_names([], home) == {}
    assert codex_names([NAMED], tmp_path / "absent") == {}


def claude_home(tmp_path):
    projects = tmp_path / "claude" / "projects" / "c--work-paper"
    projects.mkdir(parents=True)
    lines = [
        {"type": "user", "cwd": "C:/work/paper-review", "message": "secret text"},
        {"type": "ai-title", "aiTitle": "First generated title", "sessionId": CLAUDE},
        {"type": "assistant", "message": "more secret text"},
        {"type": "ai-title", "aiTitle": "Long history validation", "sessionId": CLAUDE},
    ]
    (projects / f"{CLAUDE}.jsonl").write_text(
        "\n".join(json.dumps(line, separators=(",", ":")) for line in lines) + "\n",
        encoding="utf-8",
    )
    return tmp_path / "claude", projects / f"{CLAUDE}.jsonl"


def test_claude_names_use_the_latest_title_and_a_rename_wins(tmp_path):
    home, transcript = claude_home(tmp_path)
    assert claude_names([CLAUDE, "../escape", "*"], home) == {
        CLAUDE: {"title": "Long history validation", "folder": "paper-review", "agent": None}
    }
    with transcript.open("a", encoding="utf-8") as stream:
        stream.write(json.dumps({"type": "custom-title", "customTitle": "Paper appendix"}) + "\n")
        stream.write(json.dumps({"type": "ai-title", "aiTitle": "Later generated"}) + "\n")
    assert claude_names([CLAUDE], home)[CLAUDE]["title"] == "Paper appendix"
    assert claude_names([CLAUDE], tmp_path / "absent") == {}


def test_resolve_keys_names_by_host_and_session(tmp_path):
    home, _ = claude_home(tmp_path)
    names = resolve(
        [("codex", NAMED), ("claude", CLAUDE), ("codex", None), ("cursor", "x")],
        codex=codex_home(tmp_path),
        claude=home,
    )
    assert set(names) == {("codex", NAMED), ("claude", CLAUDE)}


def test_clean_and_folder_keep_one_short_readable_line():
    assert clean("  a\n\tb  ") == "a b"
    assert clean("x" * 100) == "x" * 79 + "…"
    assert clean("   ") is None and clean(None) is None
    assert folder(r"C:\Users\someone\project\\") == "project"
    assert folder("/srv/app") == "app" and folder("") is None


def record(
    identity, title, created, *, host="codex", session="s1", before=1000, after=600, **extra
):
    return {
        "id": identity,
        "title": title,
        "created_utc": created,
        "host": host,
        "session_id": session,
        "origin_host": host,
        "origin_session_id": session,
        "preparation_id": extra.pop("preparation_id", None),
        "input_estimated_tokens": before,
        "output_estimated_tokens": after,
        "reduced_tokens": before - after,
        **extra,
    }


def test_snapshots_group_into_named_imported_and_unlinked_conversations():
    records = [
        record("c", "Third task", "2026-10-23T03:00:00+00:00", preparation_id="r3"),
        record(
            "i",
            "Imported task",
            "2026-10-23T02:30:00+00:00",
            host=None,
            session=None,
            origin_host="codex",
            origin_session_id="far-thread",
        ),
        record("b", "Second task", "2026-10-23T02:00:00+00:00", session="s2"),
        record("a", "First task", "2026-10-23T01:00:00+00:00", preparation_id="r1"),
        record("u", "Loose task", "2026-10-22T01:00:00+00:00", session=None),
    ]
    savings = {
        "r1": {
            "host": "codex",
            "session_id": "s1",
            "tokens_saved": 500,
            "money": 0.005,
            "model": "m",
        },
        "r3": {
            "host": "codex",
            "session_id": "s1",
            "tokens_saved": 700,
            "money": None,
            "model": None,
        },
        # A compressed request of the same chat whose text was not saved still counts.
        "r9": {
            "host": "codex",
            "session_id": "s1",
            "tokens_saved": 300,
            "money": 0.003,
            "model": "m",
        },
    }
    groups = group_conversations(
        records,
        names={("codex", "s1"): {"title": "Fix the cat", "folder": "TOMC", "agent": None}},
        savings=savings,
        sessions={("codex", "s1"): {"enabled": False, "project": "/w/TOMC"}},
        imported={"i": "Remote chat"},
    )
    assert [group["key"] for group in groups] == [
        ("session", "codex", "s1"),
        ("imported", "codex", "far-thread"),
        ("session", "codex", "s2"),
        ("unlinked", "codex", None),
    ]
    chat = groups[0]
    assert chat["title"] == "Fix the cat" and chat["first_title"] == "First task"
    assert [row["id"] for row in chat["records"]] == ["c", "a"]
    assert chat["records"][0]["request"]["tokens_saved"] == 700
    assert chat["tokens_saved"] == 1500 and chat["requests"] == 3
    assert chat["money"] == 0.008 and chat["enabled"] is False
    assert groups[1]["title"] == "Remote chat"
    # Without a host name or request records, the first task names it and snapshots count.
    assert groups[2]["title"] is None and groups[2]["first_title"] == "Second task"
    assert groups[2]["tokens_saved"] == 400 and groups[2]["money"] is None
    assert groups[2]["enabled"] is None
    assert conversation_key({"host": None, "session_id": None}) == ("unlinked", None, None)
