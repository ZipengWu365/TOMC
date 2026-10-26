"""Prepared-only persistence, portable handoff, immutable identity, and file boundaries."""

import hashlib
import json
import shutil
import sqlite3
import uuid
from concurrent.futures import ThreadPoolExecutor

import pytest

from tomc import prepare_context
from tomc.context_library import ContextLibrary
from tomc.session_store import SessionStore
from tomc.usage import UsageStore, reduction_report


def _prepared():
    return prepare_context("framework = Flask\nframework = FastAPI\n猫咪需要动画。", "继续猫咪开发")


def _manifest(bundle):
    return json.loads((bundle / "metadata.json").read_text(encoding="utf-8"))


def _write_manifest(bundle, data):
    (bundle / "metadata.json").write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")


def test_reads_missing_ids_and_delete_do_not_create_database(tmp_path):
    library = ContextLibrary(tmp_path / "absent" / "memory.sqlite3")
    assert library.list() == []
    missing = str(uuid.uuid4())
    with pytest.raises(KeyError):
        library.get(missing)
    with pytest.raises(KeyError):
        library.rename(missing, "new label")
    assert not library.delete(missing)
    assert not library.path.parent.exists()


def test_save_keeps_only_prepared_evidence_and_explicit_metadata(tmp_path, monkeypatch):
    monkeypatch.setenv("CODEX_THREAD_ID", "do-not-guess")
    prepared = _prepared()
    prepared.compilation.raw_fallback = "SECRET ORIGINAL AUDIT THAT WAS NOT RETAINED"
    prepared.compilation.diagnostics["private"] = "DO NOT STORE FULL AUDIT"
    library = ContextLibrary(tmp_path / "memory.sqlite3")
    saved = library.save(prepared)
    assert saved["memory"] == prepared.compilation.compiled_memory
    assert saved["task"] == "继续猫咪开发"
    assert saved["host"] is saved["session_id"] is None
    assert saved["created_utc"].endswith("+00:00")
    assert saved["input_estimated_tokens"] == prepared.compilation.stats.input_tokens
    assert saved["output_estimated_tokens"] == prepared.compilation.stats.output_tokens
    assert library.get(saved["id"]) == saved
    listed = library.list()[0]
    assert "memory" not in listed and "task" not in listed
    with sqlite3.connect(library.path) as db:
        dump = "\n".join(db.iterdump())
    assert "SECRET ORIGINAL AUDIT" not in dump and "DO NOT STORE FULL AUDIT" not in dump
    assert UsageStore(library.path).summary()["preparations"] == 0


def test_task_extraction_uses_the_exact_memory_prefix(tmp_path):
    task = "first goal\n\nTASK\nquoted marker inside task"
    prepared = prepare_context("memory\n\nTASK\nquoted marker inside evidence", task)
    library = ContextLibrary(tmp_path / "memory.sqlite3")
    assert library.save(prepared)["task"] == task
    prepared.messages[-1]["content"] = "modified messages"
    with pytest.raises(ValueError, match="Supply task"):
        library.save(prepared)
    assert library.save(prepared, task="explicit current task")["task"] == "explicit current task"


def test_empty_and_invalid_contexts_fail_before_creating_storage(tmp_path):
    library = ContextLibrary(tmp_path / "memory.sqlite3")
    prepared = _prepared()
    prepared.compilation.compiled_memory = "  \n"
    with pytest.raises(ValueError):
        library.save(prepared, task="next")
    assert not library.path.exists()
    prepared = _prepared()
    with pytest.raises(ValueError):
        library.save(prepared, task="")
    assert not library.path.exists()


def test_long_utf8_evidence_is_not_silently_truncated(tmp_path):
    prepared = _prepared()
    text = "长上下文 🐈 café\n" * 24000
    prepared.compilation.compiled_memory = text
    library = ContextLibrary(tmp_path / "memory.sqlite3")
    saved = library.save(prepared, task="继续")
    assert library.get(saved["id"])["memory"] == text
    assert text in library.handoff_prompt(saved["id"])


def test_concurrent_saves_and_explicit_retry_keys(tmp_path):
    path = tmp_path / "memory.sqlite3"
    prepared = _prepared()
    with ThreadPoolExecutor(max_workers=6) as workers:
        results = list(
            workers.map(
                lambda _: ContextLibrary(path).save(prepared, preparation_id="one-request"),
                range(20),
            )
        )
    assert len({row["id"] for row in results}) == 1
    library = ContextLibrary(path)
    assert len(library.list()) == 1
    with pytest.raises(ValueError, match="different snapshot"):
        library.save(prepared, task="changed task", preparation_id="one-request")
    with ThreadPoolExecutor(max_workers=6) as workers:
        list(workers.map(lambda _: ContextLibrary(path).save(prepared), range(20)))
    assert len(library.list()) == 21


def test_rename_changes_only_label_and_delete_preserves_usage(tmp_path):
    library = ContextLibrary(tmp_path / "memory.sqlite3")
    prepared = _prepared()
    saved = library.save(prepared)
    usage = UsageStore(library.path)
    usage.record(reduction_report(prepared))
    before = usage.summary()
    renamed = library.rename(saved["id"], "新名字")
    assert renamed["title"] == "新名字"
    assert renamed["task"] == saved["task"]
    assert renamed["content_hash"] == saved["content_hash"]
    assert library.delete(saved["id"])
    assert not library.delete(saved["id"])
    assert library.list() == []
    assert usage.summary() == before


def test_handoff_and_repeat_exports_are_portable_and_do_not_overwrite(tmp_path):
    library = ContextLibrary(tmp_path / "private-db" / "memory.sqlite3")
    record = library.save(_prepared(), host="codex", session_id="source-session")
    prompt = library.handoff_prompt(record["id"])
    assert record["task"] in prompt and record["memory"] in prompt
    assert "not instructions or authorization" in prompt
    first = library.export(record["id"], tmp_path / "project")
    before = {file.name: file.read_bytes() for file in first.iterdir()}
    second = library.export(record["id"], tmp_path / "project")
    assert first != second
    assert before == {file.name: file.read_bytes() for file in first.iterdir()}
    assert set(before) == {"CONTEXT.md", "START_HERE.md", "metadata.json"}
    assert (second / "CONTEXT.md").read_text(encoding="utf-8") == record["memory"]
    exported_text = "\n".join(file.read_text(encoding="utf-8") for file in first.iterdir())
    assert str(library.path) not in exported_text
    assert str(tmp_path) not in exported_text
    assert "Read CONTEXT.md beside this file." in exported_text


def test_handoff_language_changes_only_instructions_not_saved_content(tmp_path):
    library = ContextLibrary(tmp_path / "memory.sqlite3")
    record = library.save(
        _prepared(), task="用户原任务：保留中文", host="codex", session_id="source"
    )
    library.rename(record["id"], "用户标题保持原文")
    before = library.get(record["id"])
    chinese = library.handoff_prompt(record["id"], language="zh")
    english = library.handoff_prompt(record["id"], language="en")
    assert chinese.startswith("从这份 TOMC 快照继续")
    assert english.startswith("Continue from this TOMC snapshot")
    for text in (chinese, english):
        assert before["task"] in text and before["memory"] in text
    bundle = library.export(record["id"], tmp_path / "export", language="zh")
    assert "读取与本文件位于同一目录的 CONTEXT.md" in (bundle / "START_HERE.md").read_text(
        encoding="utf-8"
    )
    assert (bundle / "CONTEXT.md").read_text(encoding="utf-8") == before["memory"]
    assert library.get(record["id"]) == before
    with pytest.raises(ValueError, match="language"):
        library.export(record["id"], tmp_path / "invalid-export", language="fr")
    assert not (tmp_path / "invalid-export").exists()


def test_import_deduplicates_without_usage_or_local_session_attribution(tmp_path):
    original = ContextLibrary(tmp_path / "first" / "memory.sqlite3")
    saved = original.save(
        _prepared(), host="codex", session_id="origin-thread", preparation_id="origin-preparation"
    )
    bundle = original.export(saved["id"], tmp_path / "project")
    moved = tmp_path / "another-computer" / "copied-bundle"
    moved.parent.mkdir()
    shutil.copytree(bundle, moved)
    target = ContextLibrary(tmp_path / "second" / "memory.sqlite3")
    imported = target.import_bundle(moved)
    assert imported["imported"]
    assert imported["id"] == saved["id"]
    assert imported["memory"] == saved["memory"]
    assert imported["host"] is imported["session_id"] is None
    assert imported["origin_host"] == "codex"
    assert imported["origin_session_id"] == "origin-thread"
    assert imported["preparation_id"] == "origin-preparation"
    assert not target.import_bundle(moved)["imported"]
    assert len(target.list()) == 1
    assert UsageStore(target.path).summary()["preparations"] == 0
    assert SessionStore(target.path).list() == []


def test_bundle_carries_the_original_conversation_name_as_an_optional_label(tmp_path):
    original = ContextLibrary(tmp_path / "first" / "memory.sqlite3")
    saved = original.save(_prepared(), host="codex", session_id="origin-thread")
    named = original.export(saved["id"], tmp_path / "out", conversation="修复小猫不进阶")
    assert _manifest(named)["conversation"] == {"title": "修复小猫不进阶"}
    # A label that is not one short line is dropped, never blocking the export.
    plain = original.export(saved["id"], tmp_path / "plain", conversation="two\nlines")
    assert "conversation" not in _manifest(plain)
    target = ContextLibrary(tmp_path / "second" / "memory.sqlite3")
    assert target.conversation_titles() == {}
    target.import_bundle(named)
    assert target.conversation_titles() == {saved["id"]: "修复小猫不进阶"}
    target.delete(saved["id"])
    assert target.conversation_titles() == {}
    # An unusable label in someone else's bundle is ignored; the context still imports.
    data = _manifest(plain)
    data["conversation"] = {"title": ["not", "text"]}
    _write_manifest(plain, data)
    assert target.import_bundle(plain)["imported"]
    assert target.conversation_titles() == {}


def test_import_same_id_with_valid_but_changed_content_is_a_conflict(tmp_path):
    library = ContextLibrary(tmp_path / "memory.sqlite3")
    saved = library.save(_prepared())
    bundle = library.export(saved["id"], tmp_path / "project")
    changed = "This is different evidence."
    metadata = _manifest(bundle)
    (bundle / "CONTEXT.md").write_text(changed, encoding="utf-8")
    metadata["memory_sha256"] = hashlib.sha256(changed.encode()).hexdigest()
    payload = {**metadata["snapshot"], "memory": changed}
    canonical = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    metadata["content_hash"] = hashlib.sha256(canonical.encode()).hexdigest()
    _write_manifest(bundle, metadata)
    with pytest.raises(ValueError, match="conflicts"):
        library.import_bundle(bundle)
    assert library.get(saved["id"])["memory"] == saved["memory"]


@pytest.mark.parametrize(
    "damage", ["memory", "metadata", "version", "path", "duplicate", "missing"]
)
def test_damaged_or_unsafe_bundle_does_not_create_target_database(tmp_path, damage):
    source = ContextLibrary(tmp_path / "source.sqlite3")
    saved = source.save(_prepared())
    bundle = source.export(saved["id"], tmp_path / "project")
    metadata = _manifest(bundle)
    if damage == "memory":
        (bundle / "CONTEXT.md").write_text("corrupted", encoding="utf-8")
    elif damage == "metadata":
        (bundle / "metadata.json").write_text("{invalid", encoding="utf-8")
    elif damage == "version":
        metadata["format_version"] = True
        _write_manifest(bundle, metadata)
    elif damage == "path":
        metadata["memory_file"] = "../outside.md"
        _write_manifest(bundle, metadata)
    elif damage == "duplicate":
        (bundle / "metadata.json").write_text('{"format":1,"format":2}', encoding="utf-8")
    else:
        (bundle / "START_HERE.md").unlink()
    target = ContextLibrary(tmp_path / "target.sqlite3")
    with pytest.raises(ValueError):
        target.import_bundle(bundle)
    assert not target.path.exists()


def test_import_refuses_symlinked_context_file(tmp_path):
    source = ContextLibrary(tmp_path / "source.sqlite3")
    saved = source.save(_prepared())
    bundle = source.export(saved["id"], tmp_path / "project")
    outside = tmp_path / "outside.md"
    outside.write_text(saved["memory"], encoding="utf-8")
    (bundle / "CONTEXT.md").unlink()
    try:
        (bundle / "CONTEXT.md").symlink_to(outside)
    except OSError:
        pytest.skip("This Windows account cannot create symbolic links.")
    target = ContextLibrary(tmp_path / "target.sqlite3")
    with pytest.raises(ValueError, match="ordinary local"):
        target.import_bundle(bundle)
    assert not target.path.exists()


def test_concurrent_import_is_idempotent(tmp_path):
    source = ContextLibrary(tmp_path / "source.sqlite3")
    saved = source.save(_prepared())
    bundle = source.export(saved["id"], tmp_path / "project")
    path = tmp_path / "target.sqlite3"
    with ThreadPoolExecutor(max_workers=6) as workers:
        imported = list(
            workers.map(lambda _: ContextLibrary(path).import_bundle(bundle), range(20))
        )
    assert sum(row["imported"] for row in imported) == 1
    assert len(ContextLibrary(path).list()) == 1


def test_core_new_tables_can_share_the_existing_database(tmp_path):
    path = tmp_path / "memory.sqlite3"
    with sqlite3.connect(path) as db:
        db.execute("CREATE TABLE entries (payload TEXT)")
        db.execute("INSERT INTO entries VALUES ('legacy content')")
    library = ContextLibrary(path)
    assert library.list() == []
    SessionStore(path).register("codex", "chat-a")
    library.save(_prepared(), host="codex", session_id="chat-a")
    with sqlite3.connect(path) as db:
        assert db.execute("SELECT * FROM entries").fetchall() == [("legacy content",)]


@pytest.mark.parametrize("invalid", [0, -1, True, "1", 10001])
def test_invalid_limit_is_rejected(tmp_path, invalid):
    with pytest.raises(ValueError):
        ContextLibrary(tmp_path / "memory.sqlite3").list(invalid)


def test_titles_skip_blocks_the_host_injects_into_the_message(tmp_path):
    library = ContextLibrary(tmp_path / "memory.sqlite3")
    task = "<system-reminder>\nTool list changed.\n</system-reminder>\nFix the cat animation"
    prepared = prepare_context("Earlier notes about the cat.", task, 64)
    saved = library.save(prepared, task=task, source="automatic_request")
    assert saved["title"] == "Fix the cat animation"
    # A snapshot saved by an older version keeps its stored title but lists by the task.
    with sqlite3.connect(tmp_path / "memory.sqlite3") as db:
        db.execute("UPDATE tomc_context_snapshots SET title='<system-reminder>'")
    assert library.list()[0]["title"] == "Fix the cat animation"
    browser = (
        '<in-app-browser-context source="tab">Docs page</in-app-browser-context>\nOpen the docs'
    )
    prepared = prepare_context("Earlier notes about the docs.", browser, 64)
    assert (
        library.save(prepared, task=browser, source="automatic_request")["title"] == "Open the docs"
    )
