"""Compare budget-filling and adaptive selection on the deterministic fact-recall suite.

Usage: python benchmarks/adaptive/run.py [--budgets 4096 default] [--json out.json]
Offline and deterministic: no model calls. A regression is any fact that filling the
budget recalls and adaptive selection misses; the suite is meant to have none.
"""

from __future__ import annotations

import argparse
import inspect
import json
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from suite import all_cases  # noqa: E402

from tomc.easy import prepare_context  # noqa: E402
from tomc.tokenization import get_counter  # noqa: E402

ADAPTIVE = "adaptive" in inspect.signature(prepare_context).parameters


def run(budgets):
    counter = get_counter("regex")
    rows = []
    for case in all_cases():
        source_tokens = None
        for budget in budgets:
            outcome = {}
            for mode in ("fill", "adaptive") if ADAPTIVE else ("fill",):
                options = {"adaptive": mode == "adaptive"} if ADAPTIVE else {}
                prepared = prepare_context(case.history, case.task, budget, **options)
                memory = prepared.compilation.compiled_memory
                source_tokens = prepared.compilation.stats.input_tokens
                recalled = [all(text in memory for text in fact) for fact in case.facts]
                outcome[mode] = {
                    "tokens": counter.count(memory),
                    "recalled": recalled,
                    "route": prepared.compilation.diagnostics.get("selected_strategy"),
                }
            rows.append(
                {
                    "case": case.id,
                    "kind": case.kind,
                    "budget": budget or "default",
                    "source_tokens": source_tokens,
                    **outcome,
                }
            )
    return rows


def summarize(rows):
    table = defaultdict(lambda: defaultdict(lambda: {"facts": 0, "hit": 0, "tokens": 0, "n": 0}))
    regressions = []
    for row in rows:
        for mode in ("fill", "adaptive"):
            if mode not in row:
                continue
            cell = table[(row["kind"], row["budget"])][mode]
            cell["facts"] += len(row[mode]["recalled"])
            cell["hit"] += sum(row[mode]["recalled"])
            cell["tokens"] += row[mode]["tokens"]
            cell["n"] += 1
        if "adaptive" in row:
            for i, (a, b) in enumerate(zip(row["fill"]["recalled"], row["adaptive"]["recalled"])):
                if a and not b:
                    regressions.append(f"{row['case']} budget={row['budget']} fact#{i}")
    print(
        f"{'kind':16} {'budget':>8} | {'fill recall':>12} {'fill tokens':>11} | "
        f"{'adapt recall':>12} {'adapt tokens':>12} {'saved':>6}"
    )
    for (kind, budget), modes in sorted(table.items(), key=lambda x: (x[0][0], str(x[0][1]))):
        fill, adapt = modes["fill"], modes.get("adaptive")
        line = (
            f"{kind:16} {str(budget):>8} | {fill['hit']:>5}/{fill['facts']:<6} "
            f"{fill['tokens'] / fill['n']:>11,.0f} |"
        )
        if adapt and adapt["n"]:
            saved = 1 - adapt["tokens"] / fill["tokens"] if fill["tokens"] else 0
            line += (
                f" {adapt['hit']:>5}/{adapt['facts']:<6} {adapt['tokens'] / adapt['n']:>12,.0f}"
                f" {saved:>6.0%}"
            )
        print(line)
    print(f"regressions (fill recalled, adaptive missed): {len(regressions)}")
    for item in regressions[:30]:
        print("  ", item)
    return regressions


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--budgets", nargs="+", default=["4096", "default"])
    parser.add_argument("--json", type=Path)
    args = parser.parse_args()
    budgets = [None if b == "default" else int(b) for b in args.budgets]
    rows = run(budgets)
    regressions = summarize(rows)
    if args.json:
        args.json.write_text(json.dumps(rows, indent=1), encoding="utf-8")
    raise SystemExit(1 if regressions else 0)
