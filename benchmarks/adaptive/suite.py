"""Deterministic fact-recall cases for comparing budget-filling and adaptive selection.

Every case is synthetic and has known facts. A fact counts as recalled only when all
of its required strings appear in the prepared memory, so a value without its owner
(for example a channel without its project heading) is a miss. No model is called.
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field

NAMES = ["Priya", "Tomas", "Aiko", "Bruno", "Leila", "Mateo", "Sofia", "Kwame", "Ines", "Yusuf"]
ENTITIES = [
    "billing",
    "search",
    "checkout",
    "ledger",
    "gateway",
    "inventory",
    "notifier",
    "scheduler",
]
DAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"]
COLORS = ["amber", "cobalt", "violet", "copper", "jade", "scarlet"]
FILLER = [
    "We reviewed the {e} dashboard and agreed the empty state still needs work.",
    "{n} pasted the stack trace from the {e} worker; it points at a stale cache key.",
    "Can someone double-check the {e} migration on a copy of last week's data?",
    "The {e} tests took {k} minutes on the shared runner, which is slower than usual.",
    "I moved the {e} retro notes into the wiki so they are easier to find.",
    "{n} asked whether the {e} alerts should page at night or wait until morning.",
    "Let's keep the old {e} endpoint available for one more sprint for safety.",
    "The design review for {e} raised accessibility questions about color contrast.",
    "We saw {k} retries in the {e} logs yesterday, mostly from one tenant.",
    "{n} will send a short summary of the {e} incident to the channel later.",
    "The {e} prototype is behind a feature flag and only visible to staff.",
    "Please avoid force-pushing to the {e} branch while the review is open.",
    "Load testing for {e} reached {k} hundred requests per second before latency rose.",
    "We postponed the {e} cleanup because two people are out this week.",
    "The {e} runbook mentions an old hostname that should be updated.",
    "{n} found that the {e} export drops trailing spaces in some fields.",
    "Pairing session on {e} went well; the parser is much simpler now.",
    "We should rename the {e} config keys so they match the new schema.",
]
INSTRUCTIONS = (
    " Return only compact JSON with the requested keys, in the requested order, using exact"
    " values from the source. Do not guess missing facts or add extra keys."
)


@dataclass
class Case:
    id: str
    kind: str
    history: object
    task: str
    facts: list[list[str]] = field(default_factory=list)


def _filler(rng, count):
    lines = []
    for _ in range(count):
        template = rng.choice(FILLER)
        lines.append(
            template.format(e=rng.choice(ENTITIES), n=rng.choice(NAMES), k=rng.randint(2, 90))
        )
    return lines


def _conversation(rng, lines, inserts):
    """Wrap lines into alternating chat messages; inserts map line index -> fact text."""
    messages, current, role = [], [], "user"
    for index, line in enumerate(lines):
        if index in inserts:
            current.append(inserts[index])
        current.append(line)
        if len(current) >= rng.randint(2, 5):
            messages.append({"role": role, "content": "\n".join(current)})
            current, role = [], "assistant" if role == "user" else "user"
    if current:
        messages.append({"role": role, "content": "\n".join(current)})
    return messages


def conversation_cases(seed=7):
    rng = random.Random(seed)
    cases = []
    for size in (300, 1200, 3500, 10000):  # filler lines, roughly 4K to 130K estimated tokens
        for variant in range(3):
            lines = _filler(rng, size)
            entity, other = rng.sample(ENTITIES, 2)
            person, day = rng.choice(NAMES), rng.choice(DAYS)
            depth = [0.1, 0.5, 0.9][variant]
            spot = int(size * depth)
            v1, v2 = rng.sample(range(15, 120), 2)
            third = [rng.choice(NAMES) for _ in range(3)]
            owners = rng.sample(ENTITIES, 3)
            # Distinct facts at different depths; the update chain spans the history.
            facts = {
                "window": f"For the {entity} rollout we agreed the release window is {day} at 14:00.",
                "paraphrase": f"{person} will take over paging duty for {other} starting next sprint.",
                "set": f"Set the request timeout for {entity} to {v1} seconds.",
                "change": f"Change the request timeout for {entity} to {v2} seconds.",
                "revert": f"Revert the request timeout for {entity} back to {v1} seconds.",
            }
            inserts = {
                spot: facts["window"],
                max(0, spot - size // 3): facts["paraphrase"],
                int(size * 0.05): facts["set"],
                int(size * 0.45): facts["change"],
                int(size * 0.85): facts["revert"],
            }
            for i, (svc, who) in enumerate(zip(owners, third)):
                inserts[int(size * (0.2 + 0.25 * i)) + 1] = (
                    f"The owner of the {svc} service is {who}."
                )
                for d in range(4):  # superseded look-alikes near each true owner line
                    inserts[int(size * (0.15 + 0.25 * i)) + d * 3 + 2] = (
                        f"An earlier draft listed {rng.choice(NAMES)} as owner of the {svc} service; "
                        "that draft was superseded."
                    )
            history = _conversation(rng, lines, inserts)
            tag = f"conv{size}-{variant}"
            cases += [
                Case(
                    f"{tag}-window",
                    "direct",
                    history,
                    f"When is the release window for the {entity} rollout?",
                    [[facts["window"]]],
                ),
                Case(
                    f"{tag}-paraphrase",
                    "paraphrase",
                    history,
                    f"Who is on call for {other} from next sprint?",
                    [[facts["paraphrase"]]],
                ),
                # Only the service name is shared with the fact: the hardest case for lexical selection.
                Case(
                    f"{tag}-hard-paraphrase",
                    "hard-paraphrase",
                    history,
                    f"Who handles night alerts for {other} later on?",
                    [[facts["paraphrase"]]],
                ),
                Case(
                    f"{tag}-update",
                    "update",
                    history,
                    f"What is the current request timeout for {entity}?",
                    [[facts["revert"]]],
                ),
                Case(
                    f"{tag}-owners",
                    "multi-entity",
                    history,
                    f"Who owns the {owners[0]}, {owners[1]} and {owners[2]} services?"
                    + INSTRUCTIONS,
                    [[f"The owner of the {s} service is {w}."] for s, w in zip(owners, third)],
                ),
            ]
    return cases


def trap_cases(seed=11):
    """Every task word appears in unrelated lines while the answer is worded differently.

    Lexical checks cannot tell these apart; only a margin of extra lines protects the
    answer, so they measure how much the adaptive floor gives up against filling.
    """
    rng = random.Random(seed)
    cases = []
    for size in (300, 1200, 3500, 10000):
        for variant in range(3):
            lines = _filler(rng, size)
            other, person = rng.choice(ENTITIES), rng.choice(NAMES)
            fact = f"{person} will take over paging duty for {other} starting next sprint."
            inserts = {int(size * [0.2, 0.5, 0.8][variant]): fact}
            for d in range(20):
                inserts[int(size * (d + 0.5) / 20) + 1] = (
                    f"{rng.choice(NAMES)} said the new parser handles {other} night alerts "
                    "later on without retries."
                )
            history = _conversation(rng, lines, inserts)
            cases.append(
                Case(
                    f"trap{size}-{variant}",
                    "trap-paraphrase",
                    history,
                    f"Who handles night alerts for {other} later on?",
                    [[fact]],
                )
            )
    return cases


def note_cases():
    """Project notes in the shape of the external long-note test, authored independently."""
    projects = ["Aurora", "Basalt", "Cinder"]
    channels, reviewers = ["amber", "cobalt", "violet"], ["Priya", "Tomas", "Aiko"]
    blockers = ["security sign-off", "restore test", "capacity review"]

    def note(i, channel):
        name = projects[i]
        body = [
            f"---\nproject: {name.lower()}\nstatus: confirmed\n---\n# {name}\n",
            "## Current decisions",
            f"The current release channel is **{channel}**.",
            f"The current release reviewer is **{reviewers[i]}**.",
            "These are the confirmed current choices for this project only.",
            "## Historical delivery records",
        ]
        for n in range(30):
            body += [
                f"### Archived item {name[:3].upper()}-{100 + n}",
                f"The {ENTITIES[(n + i) % len(ENTITIES)]} trial used {100 + 7 * n + i} records.",
                "An early proposal used the silver channel with reviewer Theo; that proposal was",
                "superseded and must not replace the current release decisions.",
                "This entry gives historical context; it makes no current approval claim.",
            ]
        body += [
            "## Release gates",
            f"The current unresolved release blocker is **{blockers[i]}**.",
            "It remains pending; there is no recorded approval or release date.",
        ]
        return "\n".join(body)

    cases = []
    for label, changed in (("A", None), ("B", "jade"), ("A-reverted", None)):
        notes = [note(i, changed if (changed and i == 0) else channels[i]) for i in range(3)]
        expected_channel = [changed if (changed and i == 0) else channels[i] for i in range(3)]
        task = (
            "For Aurora, Basalt and Cinder, report the current release channel, reviewer and "
            "unresolved release blocker." + INSTRUCTIONS
        )
        facts = []
        for i, name in enumerate(projects):
            facts.append(
                [f"# {name}", f"The current release channel is **{expected_channel[i]}**."]
            )
            facts.append([f"# {name}", f"The current release reviewer is **{reviewers[i]}**."])
            facts.append(
                [f"# {name}", f"The current unresolved release blocker is **{blockers[i]}**."]
            )
        cases.append(Case(f"notes-{label}", "notes", "\n\n".join(notes), task, facts))
    return cases


def all_cases():
    return note_cases() + conversation_cases() + trap_cases()
