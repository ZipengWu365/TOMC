"""Adaptive selection: stop below the budget when the task's evidence is unambiguous.

The budget stays the ceiling. Selection shrinks only when every content word of the
task occurs in the history and the strongest matching lines form a small, clearly
separated group. Otherwise the ordinary budget-filling retrieval runs unchanged, so
an uncertain case keeps exactly what it kept before. Kept lines bring their
headings, the neighbours of wrapped sentences and the few lines that share their
rare names or values (the next step of a two-step question), and a small floor of
further high-scoring lines is added as a margin.
"""

from __future__ import annotations

import math
import re
from collections import Counter

from .ledger import pack_rows, raw_rows
from .schemas import Source
from .strategies.base import StrategyOutput
from .strategies.baselines import RetrievalStrategy
from .tokenization import TokenCounter

_WORD = re.compile(r"[㐀-鿿]|[a-zA-Z0-9_]+")
_CJK = re.compile(r"[㐀-鿿]")
# Grammar words, and words that frame or format a request rather than name its subject.
_IGNORED = set(
    """a an the and or but if then else of in on at to for from by with about as into over after
    before between during under above is are was were be been being do does did done have has had
    will would should can could may might must shall this that these those it its they them their
    we our us you your i me my he she his her who whom whose what which when where why how not no
    yes all any each every some such only also just than too very there here so up out off again
    please report return give provide list show tell answer respond reply use using json compact
    key keys array object objects boolean code fence format output exact exactly value values extra
    guess missing fact facts requested request order source sources document documents note notes
    without whether follow rules rule workspace one same new get make add want need know find look
    help like based according""".split()
)
# Words about time that sharpen a match when the history uses them but are not required.
_SOFT = {"current", "currently", "latest", "now", "today", "still"}
ANCHOR_RATIO = 0.5  # lines within half of the best score form the evidence core
COMPLETE_RATIO = 0.25  # weakest line accepted to cover a word the core misses
TIE_RATIO = 0.9  # when covering a word, keep every line nearly as strong as the best one
MAX_CORE_LINES = 80
MAX_CORE_SHARE = 0.4  # the core may use at most this share of the budget
FLOOR = 768  # never shrink below this size or FLOOR_SHARE of the budget, whichever is larger
FLOOR_SHARE = 0.25
LINKED_LINES = 8  # a kept line's name or value found in at most this many lines links to them


def stem(word: str) -> str:
    """A light English stemmer: owns/owner/owned -> own, services -> servic."""
    if not word.isascii() or not word.isalpha() or len(word) <= 3:
        return word
    if word.endswith("ies") and len(word) > 4:
        word = word[:-3] + "y"
    elif word.endswith("sses"):
        word = word[:-2]
    elif word.endswith("s") and not word.endswith("ss"):
        word = word[:-1]
    for suffix in ("ing", "ed", "er"):
        if word.endswith(suffix) and len(word) - len(suffix) >= 3:
            word = word[: -len(suffix)]
            if len(word) > 3 and word[-1] == word[-2] and word[-1] not in "lsz":
                word = word[:-1]
            break
    if word.endswith("e") and len(word) > 3:
        word = word[:-1]
    return word


def words(text: str) -> list[str]:
    return [stem(w) for w in _WORD.findall(text.lower())]


def content_terms(task: str) -> set[str]:
    return {
        stem(w)
        for w in _WORD.findall(task.lower())
        if w not in _IGNORED and w not in _SOFT and len(w) > 1
    }


def _scores(
    units: list[Source], docs: list[Counter], terms: set[str]
) -> list[tuple[float, Source, set[str]]]:
    df = Counter(t for d in docs for t in d)
    average = sum(sum(d.values()) for d in docs) / len(docs) or 1
    rows = []
    for unit, doc in zip(units, docs):
        length = sum(doc.values())
        matched, score = set(), 0.0
        for term in terms:
            tf = doc[term]
            if not tf:
                continue
            matched.add(term)
            idf = math.log(1 + (len(units) - df[term] + 0.5) / (df[term] + 0.5))
            score += idf * tf * 2.5 / (tf + 1.5 * (0.25 + 0.75 * length / average))
        rows.append((score, unit, matched))
    return rows


_VALUES = re.compile(r"\*\*[^*]+\*\*|\b[A-Z][\w'-]*|\b\d[\d.,:]*")


def _claims(core: set[str], units: list[Source]) -> int:
    """Largest group of strong lines repeating one sentence with different names or values.

    Lines under different top-level headings (one per project) are separate claims; the
    same sentence repeated with changing names elsewhere means the history, not a single
    line, decides which value holds.
    """
    groups = Counter()
    title = {}
    for unit in units:
        heading = re.match(r"\s*#\s+(.+)", unit.text)
        if heading:
            title[unit.message_index] = heading.group(1).strip()
        if unit.source_id in core:
            groups[(_VALUES.sub("#", unit.text.strip()), title.get(unit.message_index, ""))] += 1
    return max(groups.values(), default=0)


def _linked(core: set[str], units: list[Source], docs: list[Counter], terms: set[str]) -> set[str]:
    """Lines sharing a rare name or value with the core: the next step of a two-step question.

    "The ledger service is owned by Saffron." brings "Saffron reports to Oberon.", which
    shares no word with "Who manages the owner of the ledger service?".
    """
    names = set()
    for unit in units:
        if unit.source_id in core:
            for value in _VALUES.findall(unit.text):
                names.update(
                    stem(w)
                    for w in _WORD.findall(value.lower())
                    if w not in _IGNORED and w not in _SOFT and len(w) > 1
                )
    names -= terms
    lines = {name: [] for name in names}
    for unit, doc in zip(units, docs):
        for name in names.intersection(doc):
            lines[name].append(unit.source_id)
    return {i for ids in lines.values() if len(ids) <= LINKED_LINES for i in ids} - core


def _wrapped(text: str) -> bool:
    return not re.search(r"[.!?:;。！？)\]}*`\"']\s*$", text.strip())


def _with_context(chosen: set[str], units: list[Source]) -> set[str]:
    """Add each kept line's headings and the lines its sentence continues into."""
    kept = set(chosen)
    for i, unit in enumerate(units):
        if unit.source_id not in chosen:
            continue
        seen_levels = set()
        for j in range(i - 1, -1, -1):
            other = units[j]
            if other.message_index != unit.message_index:
                break
            heading = re.match(r"\s*(#{1,6})\s", other.text)
            if heading and len(heading.group(1)) not in seen_levels:
                seen_levels.add(len(heading.group(1)))
                kept.add(other.source_id)
                if len(heading.group(1)) == 1:
                    break
        previous = units[i - 1] if i else None
        if previous and previous.message_index == unit.message_index and _wrapped(previous.text):
            kept.add(previous.source_id)
        following = units[i + 1] if i + 1 < len(units) else None
        if following and following.message_index == unit.message_index and _wrapped(unit.text):
            kept.add(following.source_id)
    return kept


def adaptive_selection(
    units: list[Source], task: str, budget: int, counter: TokenCounter
) -> tuple[set[str] | None, str]:
    """Source IDs to keep, or None with the reason to fill the budget instead."""
    if _CJK.search(task):
        return None, "Chinese and other CJK tasks fill the budget for now."
    terms = content_terms(task)
    if not terms:
        return None, "The task names no content words to match."
    docs = [Counter(words(u.text)) for u in units]
    vocabulary = set().union(*docs)
    absent = sorted(terms - vocabulary)
    if absent:
        return (
            None,
            f"Task words absent from the history ({', '.join(absent[:5])}); the answer may be worded differently.",
        )
    soft = {stem(w) for w in _WORD.findall(task.lower()) if w in _SOFT} & vocabulary
    scored = _scores(units, docs, terms | soft)
    best = max(score for score, _, _ in scored)
    if best <= 0:
        return None, "No line matches the task."
    core = {u.source_id for score, u, _ in scored if score >= ANCHOR_RATIO * best}
    covered = set().union(*(m for score, u, m in scored if u.source_id in core))
    for term in sorted(terms - covered):
        candidates = [(s, u) for s, u, m in scored if term in m and s >= COMPLETE_RATIO * best]
        if not candidates:
            return None, f"No strong line contains '{term}'."
        strongest = max(s for s, _ in candidates)
        # Every near-tie: three projects' channel lines look alike and all are needed.
        core.update(u.source_id for s, u in candidates if s >= TIE_RATIO * strongest)
    if len(core) > MAX_CORE_LINES:
        return None, f"{len(core)} lines match about equally; the evidence is not concentrated."
    if _claims(core, units) >= 3:
        return (
            None,
            "Strong lines repeat one claim with different values; keep the surrounding history.",
        )
    kept = _with_context(core, units)
    by_id = {u.source_id: u for u in units}

    def measure(ids):
        return counter.count("\n".join(row for _, row in raw_rows([by_id[k] for k in ids])))

    size = measure(kept)
    linked = _with_context(_linked(core, units, docs, terms | soft), units) - kept
    extra = measure(linked) if linked else 0
    if size + extra > MAX_CORE_SHARE * budget:
        return None, "The matching evidence is too large to shrink safely."
    floor = min(budget, max(FLOOR, int(FLOOR_SHARE * budget)))
    for score, unit, _ in sorted(scored, key=lambda x: (-x[0], x[1].order)):
        if size >= floor or score <= 0:
            break
        if unit.source_id in kept:
            continue
        kept.add(unit.source_id)
        size += counter.count(f"[RAW {unit.source_id}] {unit.text}")
    if size + extra > budget:
        return None, "The matching evidence and its linked lines do not fit the budget."
    reason = f"Kept {len(core)} strongly matching lines with their context"
    if linked:
        reason += f" and {len(linked)} lines sharing their names or values"
    return kept | linked, reason + "."


class AdaptiveRetrievalStrategy:
    """Lexical retrieval that stops early only when the evidence is unambiguous.

    It keeps the ``rag`` method name; diagnostics report whether the evidence shrank.
    """

    name = "rag"

    def compress(
        self, history: str, units: list[Source], query: str, budget: int, counter: TokenCounter
    ) -> StrategyOutput:
        kept, reason = adaptive_selection(units, query, budget, counter)
        if kept is None:
            output = RetrievalStrategy().compress(history, units, query, budget, counter)
            output.diagnostics.update({"adaptive": "filled", "adaptive_reason": reason})
            return output
        evidence = [u for u in units if u.source_id in kept]
        text, packed = pack_rows(raw_rows(evidence), budget, counter)
        return StrategyOutput(
            text,
            "bm25_adaptive",
            evidence=[u for u in evidence if u.source_id in packed],
            raw_fallback=text,
            warnings=["Adaptive lexical selection kept less than the budget allows."],
            diagnostics={"adaptive": "shrunk", "adaptive_reason": reason},
        )
