"""Latest-value safeguards around the paper kernels, which stay unchanged.

The paper's parser reads only whole ``key = value`` lines, so a value changed later
in plain words ("scratch that, keep Flask", "db 改成 mysql 了") still looked current.
This adapter widens the state-line syntax the kernel reads, puts the task's keys and
the most recently changed values first, marks a compiled value as uncertain when a
later line may have changed it, counts the terms a question asks about (Chinese
included), and splits a paragraph too long for the budget into sentence pieces.
"""

from __future__ import annotations

import bisect
import re
import unicodedata
from collections.abc import Sequence
from dataclasses import replace
from functools import lru_cache

from .._vendor import reference as ref
from ..schemas import Source
from ..tokenization import TokenCounter

UNCAPPED = 10**9
SPLIT_SHARE = 0.25  # a line longer than this share of the budget is split into sentences
SPLIT_PIECE = 24  # smallest piece size in tokens; pieces grow to 1/32 of the budget

_FENCE = re.compile(r"^\s*(?:```|~~~)")
_BULLET = re.compile(r"^\s*(?:[-*+•]|\d{1,3}[.)])\s+")
# Words that introduce an assignment without being part of it: "Update: db = mysql".
_LABEL = re.compile(
    r"^(?:(?:ok(?:ay)?|so|and|then|actually|well|alright|updated?|updates|correction|fyi|note|"
    r"edit|decision|final(?:\s+decision)?|new|now|更新|更正|最终|最新|现在|注意)"
    r"(?:\s*[:：,，]\s*|\s+))+",
    re.I,
)
_KEY = r"[^\W\d][\w.-]*"
_ASSIGN = re.compile(rf"^({_KEY})\s*(?<![!<>=])=(?!=)\s*(.+?)\s*$")
_META = re.compile(r"^\s*[\w.-]+\s*:")
_SPEAKER = re.compile(r"^(?:[A-Z][a-z]+|user|assistant|human|ai|system)\s*:\s+(?=.*=)")
_COLON = re.compile(rf"^({_KEY})\s*:\s*(\S.*?)\s*$")
_WIDE = str.maketrans({"＝": "=", "：": ":", "；": ";"})
_TRAILING = re.compile(r"(?:\s+(?:from now on|going forward|instead|now))+\s*[.。]?$", re.I)
# Colon lines that are speakers, labels or links rather than settings.
_NOT_KEYS = set(
    """user assistant human ai system tool claude codex chatgpt gpt bot q a note notes nb task
    todo update updates correction example warning error info debug fyi ps re fwd eg ie step
    question answer summary tip hint important reminder http https ftp file mailto see edit
    subject from to cc date time""".split()
)
_CHAT_PARTICLES = re.compile(r"[了吧吗呢啊呀哦嗯我你他她们]")
_HYPOTHETICAL = re.compile(
    r"\b(?:if you|you (?:would|could|can|might)|for example|for instance|e\.g\.|example|"
    r"suppose|hypothetical(?:ly)?|demo only|not our)\b|例如|比如|假如|如果|示例|举例",
    re.I,
)
_COPY_STOP = set(
    """i you we he she they it that this these those me him her them us one notes note care
    place time over turns part effect off on up out""".split()
)
# A later line with one of these words may have changed a value it mentions.
_CHANGE = re.compile(
    r"\b(?:switch(?:ed|es|ing)?|mov(?:e|ed|es|ing)|chang(?:e|ed|es|ing)|instead|"
    r"revert(?:ed|s|ing)?|undo(?:ne)?|undid|scratch that|no longer|roll(?:ed|ing)? ?back|"
    r"migrat(?:e|ed|es|ing)|replac(?:e|ed|es|ing)|remov(?:e|ed|es|ing)|drop(?:ped|s)?|"
    r"deprecat(?:e|ed)|rais(?:e|ed)|lower(?:ed)|increas(?:e|ed)|decreas(?:e|ed)|bump(?:ed)?|"
    r"updat(?:e|ed)|correction|any ?more|is now|are now|now uses?|from now on|going forward|"
    r"slip(?:ped|s)?|postpon(?:e|ed)|delay(?:ed)?|pushed back|t(?:ook|aken) over|handed over)\b"
    r"|改用|改成|改为|换成|换了|不用了|不再|撤销|回滚|改回|弃用|迁移|更正",
    re.I,
)
# Without naming a key: undo the latest change, or switch what the task asks about.
# Verbs only: "a rollback task" or "the undo stack" undoes nothing.
_UNDO = re.compile(
    r"(?<!\ba )(?<!\ban )(?<!\bthe )\b(?:undo|undid|revert(?:ed)?|scratch that|roll(?:ed)? back)\b"
    r"|撤销|回滚|改回|算了",
    re.I,
)
_SWITCH = re.compile(
    r"\b(?:correction|switch(?:ed)?|mov(?:e|ed)|migrat(?:e|ed)|instead|replac(?:e|ed))\b"
    r"|改用|改成|改为|换成|更正",
    re.I,
)
_WORDS = re.compile(r"[\w.-]+")
_CJK = re.compile(r"[\u3040-\u30ff\u3400-\u9fff\uac00-\ud7af]")
_CJK_RUN = re.compile(r"[\u3400-\u9fff]+")
_ZH_COUNT_FILLER = re.compile(
    r"出现了多少次|出现过多少次|出现多少次|一共|总共|多少次|几次|次数|频率|计数|出现|提到了|"
    r"提到|提及|说了|说过|统计|一下|历史|记录|哪些|哪个|什么|多少|我们|你们|他们|请|被|了|过|"
    r"的|是|在|有|中|里|几"
)
_COUNT_STOP = set(
    """how many much times time often was were is are be been the a an did does do mention
    mentioned mentions appear appears appeared occur occurs occurred count counts counted
    frequency frequent word words in of on to for and or history text total number what which
    there please""".split()
)


def identity(key: str) -> str:
    """One spelling per key: DB, db and full-width ｄｂ are the same key."""
    return unicodedata.normalize("NFKC", key).casefold()


@lru_cache(maxsize=4096)
def _pattern(term: str) -> re.Pattern[str] | None:
    term = identity(term)
    if not term.strip():
        return None
    if _CJK.search(term):
        return re.compile(re.escape(term))
    parts = (re.escape(part) for part in re.split(r"[_ ]+", term) if part)
    return re.compile(r"(?<!\w)" + r"[_ ]".join(parts) + r"(?!\w)")


def mentions(text: str, term: str) -> bool:
    """Whole-word, case-insensitive mention (``account_owner`` also as ``account owner``).

    CJK terms match as substrings. ``text`` may be passed already folded by ``identity``.
    """
    pattern = _pattern(term)
    return bool(pattern and pattern.search(identity(text)))


def _clean_value(value: str) -> str:
    value = _TRAILING.sub("", value).strip()
    if value.endswith(("。", ".")) and not re.search(r"\d\.$", value):
        value = value[:-1].rstrip()
    return value


def _colon_ok(key: str, value: str) -> bool:
    if identity(key) in _NOT_KEYS or value.startswith("//") or value.endswith(("?", "？")):
        return False
    if key[:1].isupper() and not key.isupper() and not re.search(r"[\d_.]", key):
        return False  # "Alice: sounds good" is a speaker, not a setting
    if len(value) > 40 or len(value.split()) > 4:
        return False
    return not (_CJK.search(key) and _CHAT_PARTICLES.search(value))


def _front_matter(evidence: Sequence[ref.SourceUnit]) -> set[str]:
    """Lines of ``---``-delimited metadata blocks of ``key: value`` lines.

    Each document's "project: aurora" describes that document; several documents in one
    history are not one project changing its name.
    """
    ids: set[str] = set()
    i = 0
    while i < len(evidence):
        if evidence[i].text.strip() == "---":
            j = i + 1
            while j < len(evidence) and j - i <= 30 and _META.match(evidence[j].text):
                j += 1
            if j > i + 1 and j < len(evidence) and evidence[j].text.strip() == "---":
                ids.update(u.source_id for u in evidence[i : j + 1])
                i = j
        i += 1
    return ids


class StateLines:
    """Parse operations from source lines for ``reference.compile_records``.

    Accepts ``key = value`` and ``key: value``, list markers (``-``, ``*``, ``1.``), a
    leading label such as ``Update:``, several ``;``-separated assignments, full-width
    ``＝``/``：`` and Unicode keys. Lines inside fenced code blocks, comparisons such as
    ``x == y``, document metadata between ``---`` lines and examples introduced as
    hypothetical are skipped. ``B copies A`` needs both sides to look like names rather
    than words ("I copy that"). Keys are compared case-insensitively and shown with
    their latest spelling. The kernel's own patterns decide copies, edges and the
    paper's ``key = value`` form, whose values are kept exactly.
    """

    def __init__(self, units: Sequence[Source]):
        self.units = {u.source_id: u for u in units}
        self.spelling: dict[str, str] = {}
        self.parsed: set[str] = set()  # lines that produced an operation
        self.code: set[str] = set()  # fence lines and lines inside fences
        self.changes: list[tuple[int, str]] = []  # (order, key) of every SET or COPY

    def __call__(self, evidence: Sequence[ref.SourceUnit]) -> list[ref.Fact]:
        facts: list[ref.Fact] = []
        fenced, message, previous = False, None, ""
        self.code |= _front_matter(evidence)
        for unit in evidence:
            if unit.source_id in self.code:
                continue
            source = self.units.get(unit.source_id)
            current = source.message_index if source else None
            if current != message:
                fenced, message, previous = False, current, ""
            if _FENCE.match(unit.text):
                fenced = not fenced
                self.code.add(unit.source_id)
                continue
            if fenced:
                self.code.add(unit.source_id)
                continue
            found = self._parse(unit, previous)
            previous = unit.text
            if found:
                self.parsed.add(unit.source_id)
                facts.extend(found)
        return facts

    def _name(self, key: str) -> str:
        self.spelling[identity(key)] = key
        return identity(key)

    def _parse(self, unit: ref.SourceUnit, previous: str) -> list[ref.Fact]:
        text = _BULLET.sub("", unit.text.translate(_WIDE), count=1).strip()
        sources = (unit.source_id,)
        m = ref._COPY_RE.match(text)
        if m:
            dst, src = m.group(1), m.group(2)
            verb = text.split()[1].lower()
            titled = dst[:1].isupper() and dst[1:].islower() and verb != "copies"
            if identity(dst) in _COPY_STOP or identity(src) in _COPY_STOP or titled:
                return []
            self.changes.append((unit.order, identity(dst)))
            return [ref.Fact("COPY", (self._name(dst), self._name(src)), sources, unit.order)]
        m = ref._EDGE_RE.match(text)
        if m:
            return [ref.Fact("EDGE", m.groups(), sources, unit.order)]
        hypothetical = previous.rstrip().endswith((":", "：")) and _HYPOTHETICAL.search(previous)
        comment = ("#" in text or "//" in text) and re.search(r"\s(?:#|//)\s*(.*)$", text)
        if hypothetical or (comment and _HYPOTHETICAL.search(comment.group(1))):
            return []
        facts = []
        for i, part in enumerate(p.strip() for p in text.split(";")):
            pair = self._assignment(part)
            if pair is None:
                if i == 0:
                    return []
                continue
            key, value = pair
            self.changes.append((unit.order, identity(key)))
            facts.append(ref.Fact("SET", (self._name(key), value), sources, unit.order))
        return facts

    def _assignment(self, text: str) -> tuple[str, str] | None:
        m = _ASSIGN.match(text)
        if m and ref._SET_RE.match(text):
            return m.group(1), m.group(2).strip()  # the paper's form, value kept exactly
        # "Priya: db = mysql" in a transcript: the speaker is not part of the assignment.
        stripped = _LABEL.sub("", _SPEAKER.sub("", text, count=1), count=1)
        m = _ASSIGN.match(stripped)
        if m:
            value = _clean_value(m.group(2))
            return (m.group(1), value) if value else None
        m = _COLON.match(stripped)
        if m:
            value = _clean_value(m.group(2))
            if value and _colon_ok(m.group(1), value):
                return m.group(1), value
        return None

    def latest_change_before(self, order: int) -> str | None:
        """The key set or copied most recently before ``order``."""
        # Lines are parsed in order, so the list is already sorted.
        i = bisect.bisect_left(self.changes, (order, ""))
        return self.changes[i - 1][1] if i else None


def _asked(key: str, query: str) -> bool:
    return mentions(query, key)


def _names_new_value(text: str) -> bool:
    """A switch that names what it switched to: "we moved to FastAPI", "改用 FastAPI".

    "按钮颜色改成了深蓝色" changes something else; without a name, or a value after
    "to", a switch is not tied to the asked key. A bare number is an amount, not a
    value: "the benchmark moved by 3 percent" names nothing.
    """
    m = _SWITCH.search(text)
    if not m:
        return False
    # The rest of the clause: "改成了深蓝色。 (note 115)" names nothing.
    after = re.split(r"[。！？!?；;，,]|\.(?:\s|$)", text[m.end() :], maxsplit=1)[0][:40]
    return bool(
        re.search(r"(?<![\w])(?:[A-Z][\w.+-]*|`[^`]+`)", after)
        or re.search(r"\bto\s+[\w.+-]+", after, re.I)
        or (_CJK.search(text) and re.search(r"[A-Za-z0-9][\w.+-]*", after))
    )


def _found(pattern: re.Pattern[str] | None, folded: str) -> bool:
    return bool(pattern and pattern.search(folded))


def _later_line(
    record: ref.Record,
    last: int,
    lines: list[tuple[Source, str, set[str]]],
    parser: StateLines,
    asked: bool,
    keys: set[str],
) -> str | None:
    """The latest later line that may change this record's value, if any.

    A line naming the key or the value (both ends, for a path) counts first. Otherwise
    an "undo" right after this key's last change, or a switch such as "Correction: we
    moved to FastAPI" that names no other key when the task asks about this one.
    """
    if record.record_type == "STATE":
        value = record.value.strip("'\"`")
        names = [_pattern(record.key)] + ([_pattern(value)] if 3 <= len(value) <= 40 else [])
        ends = []
    else:
        if record.record_type == "PATH":
            head, tail = record.key, record.value.rsplit("=> ", 1)[-1]
        else:
            head, tail = record.key.split(" --", 1)[0], record.key.rsplit("--> ", 1)[-1]
        names, ends = [], [_pattern(head), _pattern(tail)]
    loose = None
    for line, folded, words in reversed(lines):
        if line.order <= last:
            break
        if ends:
            if all(_found(p, folded) for p in ends):
                return line.source_id
            continue
        if any(_found(p, folded) for p in names):
            return line.source_id
        if loose is None:
            if _UNDO.search(folded) and parser.latest_change_before(line.order) == record.key:
                loose = line.source_id
            elif asked and _names_new_value(line.text) and not (words & keys) - {record.key}:
                loose = line.source_id
    return loose


def refine_records(
    route: ref.Route,
    records: list[ref.Record],
    units: Sequence[Source],
    query: str,
    parser: StateLines,
    cfg: ref.TOMCConfig,
) -> list[tuple[ref.Record, tuple[str, ...]]]:
    """Order and cap records by the task, and flag values a later line may have changed.

    Returns each record with the source IDs of the later lines that put it in doubt;
    a flagged record is typed ``STATE?``, ``PATH?`` or ``EDGE?`` and says so in its value.
    """
    if route == ref.Route.COUNT:
        return [(r, ()) for r in count_records(records, units, query, cfg)]
    if route not in (ref.Route.STATE, ref.Route.RELATION):
        return [(r, ()) for r in records]
    order = {u.source_id: u.order for u in units}

    def last(record):
        return max((order[s] for s in record.sources if s in order), default=-1)

    def shown(record):
        return parser.spelling.get(record.key, record.key)

    if route == ref.Route.STATE:
        # The asked keys first (by name, as the kernel lists them), then the most recently
        # changed; not simply the first 96 by name.
        def rank(r):
            asked = _asked(shown(r), query)
            return (not asked, 0 if asked else -last(r), r.key)

        records = sorted(records, key=rank)
        records = records[: cfg.max_state_rows]
    lines = []
    for u in units:
        if u.source_id in parser.parsed or u.source_id in parser.code:
            continue
        if not _announces(u.text):
            continue
        folded = identity(u.text)
        if _CHANGE.search(folded):
            words = set(_WORDS.findall(folded)) | set(re.findall(r"\w+", folded))
            lines.append((u, folded, words))
    keys = set(parser.spelling)
    out = []
    for record in records:
        asked = route == ref.Route.STATE and _asked(shown(record), query)
        later = _later_line(record, last(record), lines, parser, asked, keys) if lines else None
        if route == ref.Route.STATE:
            record = replace(record, key=shown(record))
        if later:
            record = replace(
                record,
                record_type=record.record_type + "?",
                value=f"{record.value} (later: {later})",
            )
        out.append((record, (later,) if later else ()))
    return out


@lru_cache(maxsize=1 << 16)
def _announces(text: str) -> bool:
    return bool(_CHANGE.search(text))


def announces_change(unit: Source) -> bool:
    """Whether a line says something changed ("switched", "no longer", "改成")."""
    return _announces(unit.text)


def changes_later(units: Sequence[Source], after: int) -> list[Source]:
    """Lines after ``after`` that announce a change, latest first."""
    return [u for u in reversed(units) if u.order > after and announces_change(u)]


def _cjk_terms(query: str) -> list[str]:
    terms = []
    for run in _CJK_RUN.findall(query):
        terms += [t for t in _ZH_COUNT_FILLER.split(run) if t]
    return list(dict.fromkeys(terms))


def count_records(
    records: list[ref.Record], units: Sequence[Source], query: str, cfg: ref.TOMCConfig
) -> list[ref.Record]:
    """Put the terms the question asks about first, counting Chinese terms as substrings.

    ``records`` are the kernel's uncapped COUNT rows; an asked term that never occurs
    gets an explicit ``occ=0`` row.
    """
    by_key = {r.key: r for r in records}
    asked = []
    for term in dict.fromkeys(t.rstrip(".:/-") for t in ref.lexical_tokens(query)):
        if term in _COUNT_STOP or not re.search(r"[a-z]", term):
            continue
        asked.append(by_key.get(term) or ref.Record("COUNT", term, "occ=0, support=0", (), 1.5))
    for term in _cjk_terms(query):
        occ = sum(u.text.count(term) for u in units)
        support = sum(1 for u in units if term in u.text)
        asked.append(ref.Record("COUNT", term, f"occ={occ}, support={support}", (), 1.5))
    names = {r.key for r in asked}
    return (asked + [r for r in records if r.key not in names])[: cfg.max_count_rows]


def split_long_units(units: list[Source], budget: int, counter: TokenCounter) -> list[Source]:
    """Split each line longer than a quarter of the budget into sentence pieces.

    Pieces keep the line's message and line number and get IDs such as ``u12.1``, so a
    long single paragraph can still contribute its relevant sentences. Orders are
    renumbered to stay consecutive; lines without sentence punctuation stay whole.
    """
    limit = int(SPLIT_SHARE * budget)
    if limit <= 0:
        return units
    target = max(SPLIT_PIECE, budget // 32)
    out: list[Source] = []
    changed = False
    for unit in units:
        # A token covers at least one UTF-8 byte, so short lines skip counting.
        if len(unit.text.encode()) <= limit or counter.count(unit.text) <= limit:
            out.append(unit)
            continue
        sentences = [
            s for s in re.split(r"(?<=[。！？!?；;])|(?<=\.)(?=\s)", unit.text) if s.strip()
        ]
        if len(sentences) < 2:
            out.append(unit)
            continue
        pieces, current, size = [], "", 0
        for sentence in sentences:
            cost = counter.count(sentence)
            if current and size + cost > target:
                pieces.append(current)
                current, size = "", 0
            current += sentence
            size += cost
        pieces.append(current)
        changed = True
        out += [
            replace(unit, source_id=f"{unit.source_id}.{i}", text=piece.strip())
            for i, piece in enumerate(pieces, 1)
            if piece.strip()
        ]
    if not changed:
        return units
    return [replace(u, order=i) for i, u in enumerate(out)]


def parent_id(source_id: str) -> str:
    """``u12.3`` -> ``u12``: the input line a sentence piece came from."""
    return source_id.split(".", 1)[0]
