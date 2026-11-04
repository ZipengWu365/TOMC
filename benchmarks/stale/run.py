"""Stale-value check: does prepared context keep the latest value of a fact that changed?

Usage:
    python benchmarks/stale/run.py                    # this checkout, saved as "after"
    python benchmarks/stale/run.py --src OLD/src --label before --describe "tomc 0.2.1"
    python benchmarks/stale/run.py --check            # recompute, compare, write nothing

Offline and deterministic: synthetic histories, no model calls, a few seconds. Each
history mixes routine notes and lines that discuss three facts with updates that change
each fact three to five times. Updates are ``key = value`` lines ("state"), plain words
("plain"; some do not repeat what changed, such as "Scratch that, go with Django."), or
a ``key = value`` line followed by plain-word updates ("mixed"); the history is one notes
text or a chat. For each fact
the task asks for its current value through ``prepare_context`` at 10-80% of the
history's estimated tokens and at the default budget.

A case passes when the prepared memory contains the latest value and no unflagged
STATE record asserts an older one (a record marked ``STATE?`` says a later line may
have changed it). Results go to ``results_<label>.json``; ``RESULTS.md`` tabulates
every saved label.
"""

from __future__ import annotations

import argparse
import json
import random
import sys
from collections import defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]

SEEDS = range(8)
FRACTIONS = (0.1, 0.2, 0.4, 0.6, 0.8)
BUDGETS = (*(f"{f:.0%}" for f in FRACTIONS), "default")
STYLES = ("state", "plain", "mixed")
FORMATS = ("notes", "chat")
FILLER_LINES = 400
MENTIONS = 12  # lines per fact that discuss it without changing it
TOPICS = {
    "database": ["postgres", "mysql", "sqlite", "mariadb", "cockroachdb", "duckdb"],
    "framework": ["Flask", "FastAPI", "Django", "Starlette", "Litestar", "Sanic"],
    "cache": ["redis", "memcached", "valkey", "dragonfly", "hazelcast"],
    "region": ["eu-west-1", "us-east-2", "ap-south-1", "eu-central-1", "us-west-2"],
    "rate_limit": ["100/min", "250/min", "400/min", "600/min", "800/min"],
    "owner": ["Priya", "Theo", "Mira", "Oberon", "Saffron", "Ingrid"],
    "queue": ["rabbitmq", "kafka", "sqs", "nats", "pulsar"],
    "release_channel": ["amber", "jade", "silver", "cobalt", "ivory"],
}
FIRST = "We use {v} as the {name} for now."
UPDATES = [
    "We switched the {name} to {v}.",
    "Update: the {name} is now {v}.",
    "Heads up, the {name} moved to {v} today.",
    "Decision: going with {v} for the {name} from here on.",
    "Changed the {name} to {v} after the review.",
]
# Updates that do not repeat what changed, as people write them in a running thread.
BARE_UPDATES = [
    "Correction: we moved to {v} last week.",
    "Scratch that, go with {v}.",
    "Ops switched it to {v} today.",
]
MENTION = [
    "Reviewed the {name} dashboards; the {name} alerts and the {name} runbook look fine.",
    "Someone asked whether the {name} docs cover the {name} on-call steps.",
    "The {name} graphs were quiet this week; nobody touched the {name} settings.",
]
FILLER = [
    "Reviewed the onboarding copy for the landing page and fixed two typos.",
    "Discussed the sprint retro; people want shorter standups on Mondays.",
    "Logged a flaky screenshot test in the design system storybook.",
    "Someone asked about holiday coverage for the support rota next month.",
    "Benchmarked image thumbnails; the resize step dominates upload time.",
    "Talked through naming for the analytics events in the mobile app.",
    "Paired on a CSS grid layout bug in the settings page sidebar.",
    "Noted that the staging certificate renews automatically every quarter.",
    "The weekly sync moved the demo agenda into the shared calendar.",
    "Answered a question about exporting the quarterly report as PDF.",
]


def history(seed: int, style: str):
    """Lines of one history and, per asked fact, its values in the order they were set."""
    rng = random.Random(seed)
    topics = rng.sample(sorted(TOPICS), 3)
    events, facts = [], {}
    for topic in topics:
        values = facts[topic] = rng.sample(TOPICS[topic], rng.randint(3, 5))
        positions = sorted(rng.sample(range(FILLER_LINES), len(values)))
        name = topic.replace("_", " ")
        for i, (at, value) in enumerate(zip(positions, values)):
            if style == "state" or (style == "mixed" and i == 0):
                line = f"{topic} = {value}"
            elif i == 0:
                line = FIRST.format(name=name, v=value)
            else:
                line = rng.choice(UPDATES if rng.random() < 0.6 else BARE_UPDATES)
                line = line.format(name=name, v=value)
            events.append((at, rng.random(), line))
        for at in rng.sample(range(FILLER_LINES), MENTIONS):
            events.append((at, rng.random(), rng.choice(MENTION).format(name=name)))
    events.sort()
    lines, k = [], 0
    for i in range(FILLER_LINES):
        while k < len(events) and events[k][0] == i:
            lines.append(events[k][2])
            k += 1
        lines.append(f"{FILLER[(i * 7 + seed) % len(FILLER)]} (note {i})")
    return lines, facts


def as_format(lines, form):
    if form == "notes":
        return "\n".join(lines)
    return [
        {"role": "user" if i % 2 == 0 else "assistant", "content": t} for i, t in enumerate(lines)
    ]


def check(compilation, topic, values):
    memory = compilation.compiled_memory
    latest, stale = values[-1], values[:-1]
    asserted = [
        r
        for r in compilation.ledger
        if r.included and r.kind == "STATE" and r.key.lower().replace(" ", "_") == topic
    ]
    unflagged_stale = any(r.value != latest and r.value in stale for r in asserted)
    present = latest in memory
    return {
        "latest": present,
        "unflagged_stale": unflagged_stale,
        "pass": present and not unflagged_stale,
    }


def run(prepare_context, counter):
    rows = []
    for seed in SEEDS:
        for style in STYLES:
            lines, facts = history(seed, style)
            for form in FORMATS:
                source = as_format(lines, form)
                tokens = None
                for topic, values in facts.items():
                    task = f"What is the current {topic.replace('_', ' ')}?"
                    for label in BUDGETS:
                        if tokens is None:
                            tokens = prepare_context(source, task).compilation.stats.input_tokens
                        budget = (
                            None if label == "default" else int(float(label[:-1]) / 100 * tokens)
                        )
                        result = prepare_context(source, task, budget).compilation
                        rows.append(
                            {
                                "seed": seed,
                                "style": style,
                                "format": form,
                                "topic": topic,
                                "budget": label,
                                "history_tokens": tokens,
                                "memory_tokens": counter.count(result.compiled_memory),
                                **check(result, topic, values),
                            }
                        )
    return rows


def summarize(rows):
    cells = defaultdict(lambda: [0, 0])
    for row in rows:
        for key in ((row["style"], row["format"]), ("all", "all")):
            cell = cells[(*key, row["budget"])]
            cell[0] += row["pass"]
            cell[1] += 1
    return {f"{s}/{f}/{b}": {"pass": p, "n": n} for (s, f, b), (p, n) in sorted(cells.items())}


def table(results: dict[str, dict]) -> str:
    """One row per style and format, one column per budget: pass rate per label."""
    labels = sorted(results, key=lambda x: (x != "before", x))
    head = "| style / format | " + " | ".join(BUDGETS) + " |"
    out = [head, "|" + "---|" * (len(BUDGETS) + 1)]
    for style, form in [(s, f) for s in STYLES for f in FORMATS] + [("all", "all")]:
        cells = []
        for budget in BUDGETS:
            rates = []
            for label in labels:
                c = results[label]["summary"].get(f"{style}/{form}/{budget}")
                rates.append(f"{c['pass'] / c['n']:.0%}" if c else "-")
            cells.append(" → ".join(rates))
        name = "**all**" if style == "all" else f"{style} / {form}"
        out.append(f"| {name} | " + " | ".join(cells) + " |")
    return "\n".join(out)


def report(results: dict[str, dict]) -> str:
    labels = sorted(results, key=lambda x: (x != "before", x))
    n = next(iter(results.values()))["summary"]["all/all/default"]["n"]
    return (
        "# Stale-value check\n\n"
        "Generated by `python benchmarks/stale/run.py`; offline, deterministic, no model calls.\n\n"
        f"Share of {n} questions per budget whose prepared context contains the latest value of "
        "a fact that changed three to five times, with no unflagged STATE record asserting an "
        "older value. Budgets are shares of the history's estimated tokens; *default* omits the "
        f"budget. Each cell reads {' → '.join(labels)}.\n\n"
        + table(results)
        + "\n\n"
        + "\n".join(f"- `{label}`: {results[label]['source']}" for label in labels)
        + "\n"
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--src", type=Path, default=ROOT / "src", help="tomc source tree")
    parser.add_argument("--label", default="after")
    parser.add_argument("--check", action="store_true", help="compare with saved results only")
    parser.add_argument("--describe", help="what the source tree is, for RESULTS.md")
    args = parser.parse_args()
    sys.path.insert(0, str(args.src.resolve()))
    import tomc
    from tomc.easy import prepare_context
    from tomc.tokenization import get_counter

    rows = run(prepare_context, get_counter("regex"))
    path = HERE / f"results_{args.label}.json"
    saved = {
        p.stem.removeprefix("results_"): json.loads(p.read_text(encoding="utf-8"))
        for p in sorted(HERE.glob("results_*.json"))
    }
    here = args.src.resolve() == (ROOT / "src").resolve()
    source = args.describe or f"tomc {tomc.__version__} ({'this' if here else 'another'} checkout)"
    current = {
        "source": source,
        "columns": list(rows[0]),
        "summary": summarize(rows),
        "rows": [list(r.values()) for r in rows],
    }
    print(table({**saved, args.label: current}))
    if args.check:
        same = args.label in saved and saved[args.label]["rows"] == current["rows"]
        print("unchanged" if same else f"results differ from {path.name}")
        raise SystemExit(0 if same else 1)
    rows_json = ",\n  ".join(json.dumps(r) for r in current["rows"])
    header = json.dumps({k: v for k, v in current.items() if k != "rows"}, indent=1)[:-2]
    path.write_text(f'{header},\n "rows": [\n  {rows_json}\n ]\n}}\n', encoding="utf-8")
    saved[args.label] = current
    (HERE / "RESULTS.md").write_text(report(saved), encoding="utf-8")


if __name__ == "__main__":
    main()
