"""Send only what changed since the TOMC context already in a conversation.

``ContextUpdates`` belongs to one conversation whose history keeps every context it
was given. The first preparation is sent in full. Later ones say the source is
unchanged, or list just the lines the reader saw before that now read differently,
were deleted, or have become relevant to a new task, each with its headings. Lines
already shown and still true are never repeated. A large change, or any change in
compiled records, sends a full context that replaces the earlier ones.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from .easy import PreparedContext, prepare_context
from .input import parse_history
from .ledger import normalize
from .tokenization import get_counter

FULL_SHARE = 0.6  # an update this large relative to a full context is sent in full


@dataclass
class ContextUpdate:
    """What to put in front of the next task: a full context, a change list, or a note."""

    kind: str  # "full", "update" or "unchanged"
    text: str
    prepared: PreparedContext
    changed: list[tuple[str, str, str]] = field(default_factory=list)
    removed: list[tuple[str, str]] = field(default_factory=list)
    added: list[tuple[str, str]] = field(default_factory=list)


def _key(unit):
    return unit.message_index, unit.line_number


def _headings(units):
    """Each line's enclosing headings, outermost first: ``# Lighthouse > ## Current decisions``."""
    paths, stack, message = {}, [], None
    for unit in units:
        if unit.message_index != message:
            stack, message = [], unit.message_index
        heading = re.match(r"\s*(#{1,6})\s+\S", unit.text)
        if heading:
            level = len(heading.group(1))
            stack = [h for h in stack if h[0] < level] + [(level, unit.text.strip())]
        paths[_key(unit)] = " > ".join(text for _, text in stack if text != unit.text.strip())
    return paths


class ContextUpdates:
    """Remembers what one conversation has been shown; prepare() returns only news."""

    def __init__(self, budget: int | None = None, *, adaptive: bool | None = None):
        self.budget, self.adaptive = budget, adaptive
        self.shown: dict[tuple[int, int], str] = {}
        self.records: set[tuple] = set()
        self.counter = get_counter("regex")

    def _remember(self, prepared):
        result = prepared.compilation
        self.shown = {_key(u): u.text for u in result.evidence}
        self.records = {(r.kind, r.key, r.value) for r in result.ledger if r.included}

    def prepare(self, history: object, task: str) -> ContextUpdate:
        prepared = prepare_context(history, task, self.budget, adaptive=self.adaptive)
        result = prepared.compilation
        records = {(r.kind, r.key, r.value) for r in result.ledger if r.included}
        first = not self.shown and not self.records
        if first or records != self.records:
            self._remember(prepared)
            return ContextUpdate("full", result.compiled_memory, prepared)
        _, units = normalize(parse_history(history))
        current = {_key(u): u.text for u in units}
        paths = _headings(units)
        changed = [
            (paths.get(k, ""), old, current[k])
            for k, old in sorted(self.shown.items())
            if k in current and current[k] != old
        ]
        removed = [
            (paths.get(k, ""), old) for k, old in sorted(self.shown.items()) if k not in current
        ]
        added = [
            (paths.get(_key(u), ""), u.text) for u in result.evidence if _key(u) not in self.shown
        ]
        if not (changed or removed or added):
            note = (
                "TOMC context: the source has not changed since the TOMC context earlier in "
                "this conversation. Use that context."
            )
            return ContextUpdate("unchanged", note, prepared)
        lines = [
            "TOMC context update: since the TOMC context earlier in this conversation, only "
            "the lines below differ. Everything else in that context still holds."
        ]

        def where(path):
            return f"[{path}] " if path else ""

        if changed:
            lines.append("Changed lines (the earlier version no longer holds):")
            lines += [f"- {where(p)}was: {old}\n  now: {new}" for p, old, new in changed]
        if removed:
            lines.append("Removed lines (no longer in the source):")
            lines += [f"- {where(p)}{old}" for p, old in removed]
        if added:
            lines.append("Additional lines relevant to this task:")
            lines += [f"- {where(p)}{text}" for p, text in added]
        text = "\n".join(lines)
        if self.counter.count(text) > FULL_SHARE * max(
            1, self.counter.count(result.compiled_memory)
        ):
            self._remember(prepared)
            header = "TOMC context (replaces the earlier TOMC contexts in this conversation):\n"
            return ContextUpdate("full", header + result.compiled_memory, prepared)
        for k, old in list(self.shown.items()):
            if k not in current:
                del self.shown[k]
            elif current[k] != old:
                self.shown[k] = current[k]
        self.shown.update({_key(u): u.text for u in result.evidence})
        return ContextUpdate("update", text, prepared, changed, removed, added)
