"""Render only isolated fixture UI offscreen; never launch the installed pet or open its DB."""

import argparse
import json
import os
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace

os.environ["QT_QPA_PLATFORM"] = "offscreen"
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from PySide6.QtCore import QEvent  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from tomc.context_library import ContextLibrary  # noqa: E402
from tomc.context_library_qt import ContextLibraryDialog, SessionNotice  # noqa: E402
from tomc.session_store import SessionStore  # noqa: E402
from tomc.usage_widget_qt import load_preview_fonts  # noqa: E402


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output", type=Path, default=ROOT / "outputs/session_workspace_20261022/review"
    )
    args = parser.parse_args()
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    output = args.output / stamp
    output.mkdir(parents=True, exist_ok=False)
    app = QApplication([])
    load_preview_fonts()
    with tempfile.TemporaryDirectory(prefix="tomc-context-ui-") as fixture:
        path = Path(fixture) / "isolated.sqlite3"
        library, sessions = ContextLibrary(path), SessionStore(path)
        sessions.register(
            "codex", "demo-codex", title="TOMC 接续功能验证 · 演示", project="demo-project"
        )
        sessions.register(
            "claude", "demo-claude", title="跨 Agent 接续 · 演示", project="demo-project"
        )
        sessions.set_enabled("claude", "demo-claude", False)
        for title, before, after, memory in (
            (
                "TOMC 上下文接续功能验证",
                18400,
                2450,
                "## 目标\n让已准备的上下文可以在另一个 Agent 中继续使用。\n\n"
                "## 已确认\n- 小猫保留原有外观与动画。\n- 上下文保存在本地，导出由用户选择目录。\n"
                "- 全局处理开关与保存正文开关彼此独立。\n\n"
                "## 下一步\n验证在新路径导入后能够读取正文并生成接续提示词。\n\n"
                "## 边界\n仅处理实际经过 TOMC 的请求；估算减少不等于实测账单节省。\n\n[界面演示数据，不是真实聊天记录]",
            ),
            (
                "梳理下一轮实验计划",
                6200,
                1800,
                "演示上下文：保留实验目标、已知限制与下一步核验事项。",
            ),
            ("短输入保留检查", 120, 160, "演示上下文：某些输入不会变短，增加量仍应如实显示。"),
        ):
            prepared = SimpleNamespace(
                compilation=SimpleNamespace(
                    compiled_memory=memory,
                    stats=SimpleNamespace(
                        token_budget=3000,
                        input_tokens=before,
                        output_tokens=after,
                        tokenizer="demo-text-estimate",
                    ),
                )
            )
            library.save(prepared, task=title, host="codex", session_id="demo-codex")
        status = {
            host: {
                "label": "已配置（演示）",
                "runtime_verified": False,
                "detail": "界面演示状态，未探测真实配置。",
            }
            for host in ("codex", "claude_code")
        }
        pricing = {"rate": 3.0, "label": "演示参考单价", "model": "demo", "mode": "input"}
        dialog = ContextLibraryDialog(path, integrations=status, pricing=pricing)
        dialog.mode.setText("界面预览 · 演示数据 · 尚未观察到代理请求")
        dialog.show()
        dialog.conversation_list.setCurrentRow(min(2, dialog.conversation_list.count() - 1))
        app.processEvents()
        dialog.grab().save(str(output / "contexts.png"))
        dialog.show_analysis()
        for _ in range(5):  # nested layout requests settle one pass at a time
            app.processEvents()
        dialog.grab().save(str(output / "analysis.png"))
        dialog.tabs.setCurrentIndex(dialog.tabs.count() - 1)  # settings and connections
        app.processEvents()
        dialog.grab().save(str(output / "sessions.png"))
        notice = SessionNotice(sessions)
        sessions.register("codex", "demo-codex", event="resume")
        notice.present(sessions.active())
        app.processEvents()
        notice.grab().save(str(output / "session-default-on.png"))
        sessions.register("claude", "demo-claude", event="resume")
        notice.present(sessions.active())
        app.processEvents()
        notice.grab().save(str(output / "session-disabled.png"))
        notice.close()
        empty = ContextLibraryDialog(
            Path(fixture) / "missing.sqlite3", integrations=status, pricing=None
        )
        empty.show()
        app.processEvents()
        empty.grab().save(str(output / "empty.png"))
        assert not (Path(fixture) / "missing.sqlite3").exists()
        empty.close()
        dialog.close()
        from tomc import usage_widget_qt
        from tomc.usage import UsageStore

        usage_widget_qt.load_pricing = lambda: pricing
        UsageStore(path).record(
            {
                "counter": "demo-text-estimate",
                "usable": True,
                "input_tokens": 18400,
                "memory_tokens": 2450,
                "reduced_tokens": 15950,
            }
        )
        pet = usage_widget_qt.Companion(path, test_mode=True, connect_quota=False)
        pet.timer.stop()
        pet.session_notice.hide()
        pet.toggle_details()
        app.processEvents()
        pet.details.grab().save(str(output / "pet-panel.png"))
        pet.request_activity.start("fixture-request", "codex", "demo-codex")
        pet.refresh()
        app.processEvents()
        pet.grab().save(str(output / "request-preparing.png"))
        pet.details.grab().save(str(output / "request-preparing-panel.png"))
        pet.request_activity.finish(
            "fixture-request",
            state="prepared",
            reason="optimized",
            before_tokens=18400,
            after_tokens=2450,
        )
        pet.request_activity.sent("fixture-request")
        pet.request_activity.usage(
            "fixture-request", provider_input_tokens=2600, provider_cached_tokens=800
        )
        pet.refresh()
        app.processEvents()
        pet.details.grab().save(str(output / "request-measured-panel.png"))
        dialog.refresh()
        dialog.mode.setText("界面预览 · 演示请求与用量 · 未连接真实上游")
        dialog.tabs.setCurrentIndex(0)
        dialog.show()
        app.processEvents()
        dialog.grab().save(str(output / "request-measured-contexts.png"))
        pet.request_activity.start("fixture-disabled", "claude", "demo-claude")
        pet.request_activity.finish(
            "fixture-disabled", state="passthrough", reason="session_disabled"
        )
        pet.request_activity.sent("fixture-disabled")
        pet.refresh()
        app.processEvents()
        pet.details.grab().save(str(output / "request-disabled-panel.png"))
        pet.close()
        for widget in app.topLevelWidgets():
            widget.deleteLater()
        app.sendPostedEvents(None, QEvent.Type.DeferredDelete)
    (output / "preview.json").write_text(
        json.dumps(
            {
                "fixture_only": True,
                "production_database_opened": False,
                "production_config_modified": False,
                "installed_pet_launched": False,
                "rendering": "Qt offscreen",
                "images": [p.name for p in output.glob("*.png")],
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    print(output)


if __name__ == "__main__":
    main()
