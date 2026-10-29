"""Render the homepage UI tour from production widgets and isolated example data.

Requires the widget extra and Pillow. No host account, model API or desktop capture
is used. Generated screenshots have an embedded demo label; cat forms illustrate
input-length bands rather than measured throughput or permanent growth.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("QT_SCALE_FACTOR", "1")
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))


def render(output: Path) -> None:
    from PIL import Image
    from PySide6.QtCore import QPoint
    from PySide6.QtGui import QColor, QFont, QPainter, QPixmap
    from PySide6.QtWidgets import QApplication

    from tomc import prepare_context, savings
    from tomc.context_library import ContextLibrary
    from tomc.context_library_qt import ContextLibraryDialog
    from tomc.pet_art import PetArt
    from tomc.pet_growth import request_stage
    from tomc.request_activity import RequestActivity
    from tomc.session_store import SessionStore
    from tomc.ui_language import UiLanguage
    from tomc.usage import UsageStore

    output.mkdir(parents=True, exist_ok=True)
    app = QApplication.instance() or QApplication([])
    QFont.insertSubstitution("Microsoft YaHei UI", "Noto Sans CJK SC")
    app.setFont(QFont("Noto Sans CJK SC", 10))
    specs = (
        (
            "coding",
            "Refactor the API",
            "重构 API",
            "framework = Flask\nbackup_framework copies framework\nframework = FastAPI",
            "What are the current framework and backup_framework values?",
        ),
        (
            "paper",
            "Plan the literature review",
            "规划文献综述",
            "The review covers time-series representations.\nInclude exact citations and a comparison table.\nThe next step is to check the ten selected papers.",
            "What is the review scope and next step?",
        ),
        (
            "writing",
            "Draft the release notes",
            "起草版本说明",
            "Release notes cover context compression and task handoff.\nKeep installation commands visible.\nThe next step is to review the English and Chinese drafts.",
            "What should the release notes cover and what is the next step?",
        ),
    )
    metadata = {
        "data": "synthetic example projects",
        "renderer": "production Qt widgets",
        "model_calls": 0,
        "desktop_capture": False,
        "examples": [],
    }
    with tempfile.TemporaryDirectory(prefix="tomc-homepage-") as temporary:
        base = Path(temporary)
        os.environ["CODEX_HOME"] = str(base / "codex")
        os.environ["CLAUDE_CONFIG_DIR"] = str(base / "claude")
        (base / "codex").mkdir()
        # Keep installed-machine model discovery outside this isolated UI tour.
        original_detected = savings.load_detected
        savings.load_detected = lambda path=None: {}
        try:
            for lang in ("en", "zh"):
                folder = base / lang
                folder.mkdir()
                path = folder / "examples.sqlite3"
                UiLanguage(path).set_language(lang)
                sessions, library = SessionStore(path), ContextLibrary(path)
                activity, usage = RequestActivity(path), UsageStore(path)
                names = []
                for index, (kind, en, zh, facts, task) in enumerate(specs):
                    name = en if lang == "en" else zh
                    session = f"example-{kind}"
                    names.append({"id": session, "thread_name": name})
                    sessions.register("codex", session, title=name, project="example-project")
                    background = "\n".join(
                        f"Archive entry {n}: the team discussed scheduling, routine housekeeping and document layout."
                        for n in range(100)
                    )
                    prepared = prepare_context(f"{background}\n{facts}", task, budget=800)
                    stats = prepared.compilation.stats
                    request_id = f"homepage-{lang}-{index}"
                    activity.start(request_id, "codex", session)
                    activity.finish(
                        request_id,
                        state="prepared",
                        reason="optimized",
                        before_tokens=stats.input_tokens,
                        after_tokens=stats.output_tokens,
                        context_input_tokens=stats.input_tokens,
                    )
                    usage.record(
                        {
                            "request_id": request_id,
                            "usable": True,
                            "input_tokens": stats.input_tokens,
                            "memory_tokens": stats.output_tokens,
                            "reduced_tokens": stats.input_tokens - stats.output_tokens,
                            "counter": stats.tokenizer,
                            "context_input_tokens": stats.input_tokens,
                        }
                    )
                    library.save(
                        prepared,
                        task=task,
                        host="codex",
                        session_id=session,
                        preparation_id=request_id,
                    )
                    if lang == "en":
                        metadata["examples"].append(
                            {
                                "name": name,
                                "input_estimated_tokens": stats.input_tokens,
                                "output_estimated_tokens": stats.output_tokens,
                                "counter": stats.tokenizer,
                            }
                        )
                (base / "codex/session_index.jsonl").write_text(
                    "\n".join(json.dumps(n, ensure_ascii=False) for n in names), encoding="utf-8"
                )
                status = {
                    host: {
                        "label": "UI demo",
                        "runtime_verified": False,
                        "detail": "Isolated example data",
                    }
                    for host in ("codex", "claude_code")
                }
                price = {"rate": 2.0, "label": "Demo input price", "model": "demo", "mode": "input"}
                window = ContextLibraryDialog(path, integrations=status, pricing=price)
                window.resize(1100, 920)
                window.show()
                window.refresh()
                for _ in range(8):
                    app.processEvents()
                window.conversation_list.setCurrentRow(min(2, window.conversation_list.count() - 1))
                for _ in range(6):
                    app.processEvents()

                def snapshot(name: str) -> None:
                    image = window.grab()
                    canvas = QPixmap(image.width(), image.height() + 38)
                    canvas.fill(QColor("#F2F5F3"))
                    painter = QPainter(canvas)
                    painter.setPen(QColor("#315647"))
                    painter.setFont(QFont("Noto Sans CJK SC", 10))
                    label = (
                        "UI DEMO · SYNTHETIC EXAMPLE PROJECTS · LOCAL TOKEN ESTIMATES"
                        if lang == "en"
                        else "界面演示 · 合成示例项目 · 本地 token 估算"
                    )
                    painter.drawText(18, 25, label)
                    painter.drawPixmap(QPoint(0, 38), image)
                    painter.end()
                    if not canvas.save(str(output / f"{name}-{lang}.png")):
                        raise OSError("Could not save UI preview")

                snapshot("contexts")
                window.show_analysis()
                for _ in range(8):
                    app.processEvents()
                snapshot("analysis")
                window.close()
                window.deleteLater()
        finally:
            savings.load_detected = original_detected

        art = PetArt()
        art.resize(140, 156)
        frames = []
        for frame in range(28):
            canvas = QPixmap(640, 192)
            canvas.fill(QColor("#FAF8F3"))
            painter = QPainter(canvas)
            for i, count in enumerate((1000, 12000, 120000, 1200000)):
                art.set_state(request_stage(count, "en"))
                art.phase = frame / 23 if frame < 24 else None
                art.update()
                app.processEvents()
                painter.drawPixmap(QPoint(10 + i * 160, 0), art.grab())
                painter.setPen(QColor("#625644"))
                painter.setFont(QFont("DejaVu Sans", 9))
                painter.drawText(10 + i * 160, 170, ("<10K", "10K–100K", "100K–1M", "1M+")[i])
            painter.end()
            image = canvas.toImage().convertToFormat(canvas.toImage().Format.Format_RGBA8888)
            frames.append(
                Image.frombytes(
                    "RGBA", (image.width(), image.height()), bytes(image.bits())
                ).convert("RGB")
            )
        frames[0].save(
            output / "cat-work-forms.gif",
            save_all=True,
            append_images=frames[1:],
            duration=110,
            loop=0,
            optimize=True,
        )
        art.close()
    (output / "render-metadata.json").write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(f"Rendered bilingual UI previews and cat animation to {output}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=ROOT / "assets/homepage")
    render(parser.parse_args().output.resolve())
