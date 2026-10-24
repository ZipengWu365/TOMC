"""Optional local illustrated companion. No desktop capture or computer control."""

from __future__ import annotations

import argparse
from pathlib import Path

from .store import default_store_path


def display_values(summary: dict, language=None) -> dict:
    """Do not silently pool different token counters or turn errors into zero."""
    groups = summary["by_counter"]
    english = getattr(language, "code", language) == "en"
    if len(groups) > 1:
        return {
            "total": "View by counter" if english else "分计数器查看",
            "detail": "Different counters are not combined" if english else "不同计数口径不合并",
            "before": "—",
            "after": "—",
            "calls": summary["preparations"],
        }
    group = groups[0] if groups else {}
    delta = group.get("reduced_tokens", 0)
    percent = group.get("reduction_percent")
    return {
        "total": f"{delta:,}",
        "detail": (
            (f"Reduced {percent:.2f}%" if english else f"减少 {percent:.2f}%")
            if percent is not None
            else "Waiting for the first context preparation"
            if english
            else "等待首次上下文准备"
        ),
        "before": f"{group.get('input_tokens', 0):,}",
        "after": f"{group.get('memory_tokens', 0):,}",
        "calls": summary["preparations"],
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--store", type=Path)
    parser.add_argument("--test-mode", action="store_true")
    parser.add_argument("--host", choices=("codex", "claude", "cursor", "other"), default="codex")
    parser.add_argument("--state-file", type=Path, help=argparse.SUPPRESS)
    args = parser.parse_args()
    try:
        from .usage_widget_qt import run
    except ImportError as exc:
        raise SystemExit(
            "The optional pet needs PySide6-Essentials. Install tomc-memory[widget]."
        ) from exc
    run((args.store or default_store_path()).resolve(), args.test_mode, args.state_file, args.host)


if __name__ == "__main__":
    main()
