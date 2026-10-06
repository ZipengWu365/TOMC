"""Generate original synthetic scenarios; no third-party dataset text."""

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
examples = []
history = []
for day in range(1, 13):
    history.extend(
        [
            {
                "role": "user",
                "content": f"Session {day}: We discussed the reading list and weekend plans.\n"
                f"drink = {'coffee' if day < 10 else 'tea'}\nseat = {'window' if day < 11 else 'aisle'}\n"
                f"contact = {'phone' if day < 12 else 'email'}",
            },
            {
                "role": "assistant",
                "content": "The notes have been saved. The library closes at six; "
                "the botanical garden has a new map. These are background notes, not preference updates.",
            },
        ]
    )
history.append({"role": "user", "content": "backup_drink copies drink\ndrink = decaf tea"})
examples.append(
    {
        "id": "preferences",
        "title": "01 / Preferences that change · 偏好更新",
        "messages": history,
        "query": "What are the current drink, seat, contact and backup_drink preferences?",
        "strategy": "tomc_raw",
        "budget": 320,
        "note": "Normalized assignments illustrate latest-write and snapshot-copy semantics. "
        "Free prose is not silently converted into preferences.",
    }
)
history = [
    {
        "role": "user",
        "content": "Draft a workshop itinerary.\nduration = 3 days\n"
        "format = in person\nparticipants = 20\nvenue = north hall",
    }
]
for i in range(1, 17):
    history.append(
        {
            "role": "assistant",
            "content": f"Planning note {i}: The agenda contains introductions, "
            "a shared exercise, a break, and a discussion. A draft slide layout is ready. "
            "The timetable is still provisional.",
        }
    )
history.extend(
    [
        {"role": "user", "content": "duration = 2 days\nformat = hybrid\nparticipants = 35"},
        {"role": "user", "content": "venue = online\nformat = remote\nbackup_venue copies venue"},
    ]
)
examples.append(
    {
        "id": "constraints",
        "title": "02 / Moving constraints · 任务约束",
        "messages": history,
        "query": "What are the current duration, format, participants and venue constraints?",
        "strategy": "tomc",
        "budget": 240,
        "note": "Earlier constraints should not overwrite later assignments.",
    }
)
history = [
    {
        "role": "user",
        "content": "Task: fix empty-input handling in src/parser.py. "
        "Must preserve the public parse_items() signature and add a focused regression test.",
    }
]
for i in range(1, 13):
    history.extend(
        [
            {
                "role": "assistant",
                "content": f"Inspection {i}: opened src/parser.py and tests/test_parser.py. "
                "The module converts input records to an ordered list; the fixture contains two populated rows.",
            },
            {
                "role": "tool",
                "content": "Repository note: src/parser.py defines parse_items(text). "
                "The public interface is used by src/loader.py. No changes made during this inspection.",
            },
        ]
    )
history.extend(
    [
        {
            "role": "tool",
            "content": "pytest tests/test_parser.py -q\nFAILED test_empty: IndexError at src/parser.py",
        },
        {
            "role": "assistant",
            "content": "Attempted a truthiness guard in src/parser.py; did not work, still failing test_empty.",
        },
        {
            "role": "assistant",
            "content": "Reverted the guard. Patched src/parser.py to handle an empty record list before indexing.",
        },
        {
            "role": "tool",
            "content": "pytest tests/test_parser.py -q\nFocused test_empty passed; 8 tests passed.",
        },
        {
            "role": "assistant",
            "content": "Need to run the full test suite. Full-suite status is unknown; no deployment has occurred.",
        },
    ]
)
examples.append(
    {
        "id": "agent",
        "title": "03 / A repair in progress · Agent 轨迹",
        "messages": history,
        "query": "Continue the parser repair: what failed, what changed, and what should be checked next?",
        "strategy": "tomc2",
        "budget": 720,
        "note": "Synthetic tool output: test observations are extracted, never re-executed or independently verified.",
    }
)
history = [
    {
        "role": "user",
        "content": "The community archive is organizing an evening exhibition. "
        "Mira first suggested using the garden because the natural light would suit the photographs.",
    }
]
for i in range(1, 19):
    history.append(
        {
            "role": "assistant",
            "content": f"Exhibition note {i}: The catalogue needs a contents page. "
            "The team discussed labels, frame sizes, volunteer badges, ticket designs and a sign-in table.",
        }
    )
history.extend(
    [
        {
            "role": "user",
            "content": "Mira changed the venue to the library. Her exact explanation was: "
            '"The garden path becomes slippery after rain, and the library has a step-free entrance."',
        },
        {
            "role": "assistant",
            "content": "venue = library\nDo not infer that lighting caused the final venue change; "
            "Mira's explanation is about access and rain.",
        },
    ]
)
examples.append(
    {
        "id": "evidence",
        "title": "04 / A reason needs a quote · 原文证据",
        "messages": history,
        "query": "Why did Mira change the venue? Quote her exact explanation.",
        "strategy": "hybrid",
        "budget": 260,
        "note": "A venue=library state row cannot preserve the reason. The router retains source evidence.",
    }
)
for example in examples:
    payload = json.dumps(example, ensure_ascii=False, indent=2) + "\n"
    for folder in [ROOT / "demo/examples", ROOT / "src/tomc/data"]:
        (folder / f"{example['id']}.json").write_text(payload, encoding="utf-8")
print(f"Generated {len(examples)} original scenarios.")
