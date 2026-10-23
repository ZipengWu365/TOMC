"""Synthetic Mac flow through real MCP stdio, stored snapshots and desktop actions."""

import asyncio
import json
import os
import sys

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
pytest.importorskip("PySide6")
pytest.importorskip("mcp")

from mcp import ClientSession  # noqa: E402
from mcp.client.stdio import StdioServerParameters, stdio_client  # noqa: E402
from PySide6.QtCore import QEvent  # noqa: E402
from PySide6.QtWidgets import QApplication, QFileDialog  # noqa: E402

from tomc import context_library_qt, pricing_catalog, savings  # noqa: E402
from tomc.context_library import ContextLibrary  # noqa: E402
from tomc.context_library_qt import ContextLibraryDialog  # noqa: E402
from tomc.session_hook import handle_event  # noqa: E402
from tomc.session_store import SessionStore  # noqa: E402
from tomc.usage import UsageStore  # noqa: E402

pytestmark = pytest.mark.skipif(sys.platform != "darwin", reason="macOS desktop integration")


@pytest.fixture(scope="module")
def app():
    yield QApplication.instance() or QApplication([])


@pytest.mark.parametrize("host", ["codex", "claude"])
@pytest.mark.parametrize("language", ["zh", "en"])
def test_external_history_survives_mcp_desktop_and_portable_handoff(
    app, tmp_path, monkeypatch, host, language
):
    """Enabled external preparation and pause boundaries remain distinct from host compaction."""
    database = tmp_path / "source.sqlite3"
    session_id = "synthetic-session"
    original_title = "Synthetic project conversation · 测试对话"
    handle_event(
        {
            "hook_event_name": "SessionStart",
            "session_id": session_id,
            "session_title": original_title,
        },
        host="claude_code" if host == "claude" else host,
        store=database,
    )
    sessions = SessionStore(database)
    library = ContextLibrary(database)
    assert sessions.active()["event"] == "SessionStart"
    assert sessions.effective_enabled(host, session_id)

    async def prepare_external_history():
        params = StdioServerParameters(
            command=sys.executable,
            args=["-m", "tomc", "mcp", "--store", str(database)],
        )
        async with stdio_client(params) as (read, write):
            async with ClientSession(read, write) as client:
                initialized = await client.initialize()
                assert "host manages the active conversation" in initialized.instructions
                assert "separately supplied external history" in initialized.instructions

                async def prepare(history, task="Continue the external project", budget=None):
                    arguments = {
                        "history": history,
                        "task": task,
                        "tomc_host": host,
                        "tomc_session_id": session_id,
                    }
                    if budget is not None:
                        arguments["budget"] = budget
                    return await client.call_tool("prepare_context", arguments)

                empty = await prepare("")
                assert empty.isError and library.list() == []
                sessions.set_enabled(host, session_id, False)
                paused = await prepare("Synthetic external evidence")
                assert json.loads(paused.content[0].text)["status"] == "paused"
                assert library.list() == []
                sessions.set_enabled(host, session_id, True)

                short_text = "Synthetic external evidence: the release color is teal."
                short = await prepare(short_text)
                assert not short.isError
                short_result = json.loads(short.content[0].text)
                assert short_result["memory"] == short_text
                assert short_result["context_reduction"]["reduced_tokens"] == 0

                history = "\n".join(
                    f"External decision {i}: region EU; capacity {40 + i}; retain the teal design."
                    for i in range(400)
                )
                prepared = None
                for task in ("Find the external project's region", "Continue its release plan"):
                    result = await prepare(history, task=task, budget=500)
                    assert not result.isError
                    prepared = json.loads(result.content[0].text)
                    assert prepared["status"] == "prepared"
                    assert prepared["context_record"]["status"] == "saved"
                    assert prepared["input_estimated_tokens"] > prepared["memory_estimated_tokens"]
                    assert prepared["memory_estimated_tokens"] <= 500
                    assert not prepared["request_replacement_verified"]
                sessions.update_settings(enabled=False)
                paused = await prepare(history)
                assert json.loads(paused.content[0].text)["status"] == "paused"
                assert len(library.list()) == 3
                sessions.update_settings(enabled=True)
                return prepared

    prepared = asyncio.run(prepare_external_history())
    assert UsageStore(database).summary()["preparations"] == 3
    snapshot = library.get(prepared["context_record"]["id"])
    assert snapshot["memory"] == prepared["memory"]

    # Isolate host-name/pricing lookup as well as the preparation database.
    monkeypatch.setattr(
        context_library_qt,
        "resolve",
        lambda pairs: {(host, session_id): {"title": original_title}},
    )
    monkeypatch.setattr(pricing_catalog, "read_catalog", lambda path=None: {"providers": {}})
    monkeypatch.setattr(savings, "load_detected", lambda path=None: {})
    status = {
        name: {"label": "Fixture", "runtime_verified": False} for name in ("codex", "claude_code")
    }
    source = ContextLibraryDialog(database, integrations=status, pricing=None)
    receiver = ContextLibraryDialog(
        tmp_path / "receiver.sqlite3", integrations=status, pricing=None
    )
    try:
        source.language.set_language(language)
        receiver.language.set_language(language)
        source.refresh(select_id=snapshot["id"])
        assert source.conversation_title.text() == original_title
        assert source.version_list.count() == 3
        source.copy_handoff()
        expected = library.handoff_prompt(snapshot["id"], language=language)
        assert app.clipboard().text() == expected
        assert snapshot["memory"] in expected and snapshot["task"] in expected

        export_root = tmp_path / "portable"
        monkeypatch.setattr(QFileDialog, "getExistingDirectory", lambda *a, **kw: str(export_root))
        source.export_context()
        bundle = next(export_root.iterdir())
        metadata = json.loads((bundle / "metadata.json").read_text(encoding="utf-8"))
        assert metadata["conversation"]["title"] == original_title
        assert (bundle / "CONTEXT.md").read_text(encoding="utf-8") == snapshot["memory"]
        assert snapshot["task"] in (bundle / "START_HERE.md").read_text(encoding="utf-8")

        assert receiver.conversation_list.count() == 0
        assert not receiver.copy_button.isEnabled()
        monkeypatch.setattr(QFileDialog, "getExistingDirectory", lambda *a, **kw: str(bundle))
        for _ in range(2):
            receiver.import_bundle()
            assert receiver.conversation_title.text() == original_title
            assert receiver.version_list.count() == 1
            assert receiver.selected_record["session_id"] is None
            receiver.copy_handoff()
            assert app.clipboard().text() == expected
        assert UsageStore(receiver.path).summary()["preparations"] == 0
    finally:
        app.clipboard().clear()
        for window in (source, receiver):
            window.close()
            window.deleteLater()
        app.sendPostedEvents(None, QEvent.Type.DeferredDelete)
