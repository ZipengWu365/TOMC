"""Generate the nine synthetic histories used by the Claude/Codex retention checks.

This preserves the 2026-10-02 realistic generator's text, value order and random
calls: three seeds (11, 23, 37) at 670, 1,340 and 2,700 turns. The length labels
are approximate cl100k_base history lengths, not measured model-request tokens.
Compute token counts with the tested compiler/tokenizer when preparing a run.

This standard-library-only script does not import TOMC, touch notebooks, call a
model or read personal history. Output contains synthetic inputs and expected
values, never model answers or performance measurements.

Usage:
    python scripts/benchmarks/codex_retention_cases.py --output outputs/codex_cases.json
"""

from __future__ import annotations

import argparse
import hashlib
import json
import random
from pathlib import Path

NAMES = [
    "Alice",
    "Bob",
    "Priya",
    "Chen",
    "Marta",
    "Omar",
    "Sofia",
    "Kenji",
    "Lena",
    "Tariq",
    "Grace",
    "Diego",
]

DATES = [
    "March 3",
    "March 10",
    "March 17",
    "March 24",
    "March 31",
    "April 7",
    "April 14",
    "April 21",
    "April 28",
    "May 5",
    "May 12",
    "May 19",
    "May 26",
    "June 2",
    "June 9",
    "June 16",
]

VARS = {
    "deadline": (
        DATES,
        [
            "Project update: the report deadline is now {v}.",
            "Heads-up, the report is due {v} instead.",
            "Change of plan: we submit the report on {v}.",
            "Confirmed with the client that the report deadline moves to {v}.",
        ],
    ),
    "page_limit": (
        [f"{n} pages" for n in (6, 8, 10, 12, 14, 16, 18, 20)],
        [
            "Requirement update: the report must stay under {v}.",
            "The client now caps the report at {v}.",
            "New limit for our report: {v} maximum.",
        ],
    ),
    "eval_owner": (
        NAMES,
        [
            "Ownership: {v} now owns the evaluation section.",
            "Reassigning the evaluation section to {v}.",
            "From today {v} takes over the evaluation section.",
        ],
    ),
    "intro_owner": (
        NAMES,
        [
            "{v} will write the introduction from now on.",
            "Ownership: the introduction section goes to {v}.",
            "Swapping owners: {v} now handles the introduction.",
        ],
    ),
    "meeting": (
        [
            f"{d} at {t}"
            for d in ("Monday", "Tuesday", "Wednesday", "Thursday", "Friday")
            for t in ("9am", "11am", "2pm", "4pm")
        ],
        [
            "Our weekly project sync moves to {v}.",
            "Rescheduling the project sync to {v} going forward.",
            "Project sync is now {v}.",
        ],
    ),
    "budget": (
        [f"${n:,}" for n in range(3000, 15001, 500)],
        [
            "Finance approved a project budget of {v}.",
            "The project budget is revised to {v}.",
            "Budget update for our project: {v}.",
        ],
    ),
    "venue": (
        [
            "Berlin",
            "Lisbon",
            "Toronto",
            "Osaka",
            "Nairobi",
            "Lyon",
            "Austin",
            "Seoul",
            "Porto",
            "Dublin",
        ],
        [
            "The final presentation will be held in {v}.",
            "Venue change: the final presentation is now in {v}.",
            "We booked {v} for the final presentation.",
        ],
    ),
    "reviewer": (
        NAMES,
        [
            "{v} is the external reviewer for the report now.",
            "The client named {v} as our report reviewer.",
            "New external reviewer for the report: {v}.",
        ],
    ),
}

DISTRACTORS = [
    "The cafeteria survey deadline is {date}; please fill it in.",
    "Sam's unrelated slide deck runs about {n} pages.",
    "The marketing team meets every {day} at {time}.",
    "{name} owns the evaluation of the new coffee machine, not our report.",
    "The other project's budget was cut to ${money:,}.",
    "{name} reviewed the hiring rubric last week.",
    "The holiday party might be in {city} this year.",
    "{name} is drafting an introduction email for the newsletter.",
]

NOISE = [
    "{name} shared a photo of their cat sleeping on a keyboard.",
    "Has anyone tried the new {food} place near the station? {name} says it is good.",
    "Reminder: the {thing} on floor {n} is out of order again.",
    "{name} is out sick today, hope they feel better soon.",
    "We spent ten minutes debating {topic}; no conclusion.",
    "{name} recommends the podcast about {topic}.",
    "The Wi-Fi dropped again during the {topic} call.",
    "{name} brought {food} for everyone, thanks!",
    "Quick poll: should we move the team lunch to {day}?",
    "{name} finished the {topic} training module.",
    "Can someone restart the build server? {name} says it is stuck.",
    "{name} found a typo in the onboarding wiki about {topic}.",
    "The parking garage closes early on {day} this month.",
    "{name} and {name2} are pairing on the {topic} script today.",
    "Fun fact from {name}: the office plant is {n} years old.",
]

FOOD = ["ramen", "tacos", "falafel", "dumplings", "pizza", "salad", "curry", "bagels"]

THING = ["printer", "coffee machine", "elevator", "projector", "fridge"]

TOPIC = [
    "tabs versus spaces",
    "standing desks",
    "mechanical keyboards",
    "the new logo",
    "remote Fridays",
    "unit test naming",
    "dark mode",
    "the chess tournament",
    "time zones",
    "emoji in commit messages",
]

DAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"]

QUESTIONS = {
    "deadline": "What is the current report deadline?",
    "page_limit": "What is the current page limit for the report?",
    "eval_owner": "Who currently owns the evaluation section?",
    "meeting": "When is the weekly project sync now?",
    "venue": "Where will the final presentation be held?",
}

TASK = "Answer these questions about our report project, using the latest information: " + " ".join(
    f"({i}) {q}" for i, q in enumerate(QUESTIONS.values(), 1)
)

LENGTHS = {"10k": 670, "20k": 1340, "40k": 2700}


def fill(rng, template):
    return template.format(
        name=rng.choice(NAMES),
        name2=rng.choice(NAMES),
        food=rng.choice(FOOD),
        thing=rng.choice(THING),
        topic=rng.choice(TOPIC),
        day=rng.choice(DAYS),
        time=rng.choice(["9am", "11am", "2pm", "4pm"]),
        n=rng.randint(2, 30),
        date=rng.choice(DATES),
        money=rng.randrange(3000, 15000, 500),
        city=rng.choice(VARS["venue"][0]),
    )


def build(turns: int, seed: int = 11):
    rng = random.Random(seed)
    state, lines = {}, []
    for i in range(1, turns + 1):
        r = rng.random()
        if r < 1 / 12 or (i > turns - 40 and len(state) < len(VARS)):
            key = rng.choice([k for k in VARS if k not in state] or list(VARS))
            pool, templates = VARS[key]
            value = rng.choice([v for v in pool if v != state.get(key)])
            state[key] = value
            text = rng.choice(templates).format(v=value)
        elif r < 1 / 12 + 0.12:
            text = fill(rng, rng.choice(DISTRACTORS))
        else:
            text = fill(rng, rng.choice(NOISE))
        lines.append(f"{rng.choice(NAMES)}: {text}")
    return "\n".join(lines) + "\n", state


SEEDS = (11, 23, 37)


def generate_cases() -> dict:
    """Return the deterministic task and nine synthetic histories."""
    cases = {}
    for seed in SEEDS:
        for label, turns in LENGTHS.items():
            history, state = build(turns, seed=seed)
            if len(history) > 200_000:
                raise ValueError(f"{seed}/{label} exceeds the public history limit")
            cases[f"s{seed}-{label}"] = {
                "seed": seed,
                "length": label,
                "turns": turns,
                "history": history,
                "expected": {key: state[key] for key in QUESTIONS},
                "history_sha256": hashlib.sha256(history.encode("utf-8")).hexdigest(),
            }
    return {"task": TASK, "questions": QUESTIONS, "cases": cases}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, type=Path, help="UTF-8 JSON output path")
    args = parser.parse_args()
    data = generate_cases()
    encoded = json.dumps(data, ensure_ascii=False, indent=2) + "\n"
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(encoded, encoding="utf-8", newline="\n")
    print(
        json.dumps(
            {
                "output": str(args.output.resolve()),
                "cases": len(data["cases"]),
                "sha256": hashlib.sha256(encoded.encode("utf-8")).hexdigest(),
            }
        )
    )


if __name__ == "__main__":
    main()
