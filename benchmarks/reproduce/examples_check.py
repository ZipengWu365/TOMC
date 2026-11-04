"""Run the two offline examples and check the numbers the documentation quotes.

Usage:
    python benchmarks/reproduce/examples_check.py

- examples/snapshot.py: backup_drink keeps tea, drink = decaf tea, "Estimated tokens: 31 -> 36".
- examples/api_context.py: framework = FastAPI, backup_framework = Flask, message text 138 -> 90
  under the lexical estimate.

No model calls; writes nothing.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def run(name: str) -> str:
    return subprocess.run(
        [sys.executable, str(ROOT / "examples" / name)],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
    ).stdout


def main() -> int:
    problems = []
    snapshot = run("snapshot.py")
    for needle in (
        "[STATE] backup_drink = tea",
        "[STATE] drink = decaf tea",
        "Estimated tokens: 31 -> 36",
    ):
        if needle not in snapshot:
            problems.append(f"snapshot.py: missing {needle!r}")
    api = json.loads(run("api_context.py"))
    if (api["message_text_before"], api["message_text_after"]) != (138, 90):
        problems.append(
            f"api_context.py: {api['message_text_before']} -> {api['message_text_after']}, "
            "expected 138 -> 90"
        )
    memory = api["payload"]["messages"][-1]["content"]
    for needle in ("[STATE] framework = FastAPI", "[STATE] backup_framework = Flask"):
        if needle not in memory:
            problems.append(f"api_context.py: missing {needle!r}")
    if problems:
        print("\n".join(problems), file=sys.stderr)
        return 1
    print(
        "Examples match: snapshot 31 -> 36 estimated tokens; API example 138 -> 90, FastAPI/Flask."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
