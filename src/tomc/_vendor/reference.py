"""Reference implementation for the algorithmic specification in the TOMC paper.

This module is intentionally small and explicit. It implements the paper's public
interface: source-addressable segmentation, deterministic evidence selection,
operation routing, typed compilation, provenance retention, raw backup, and
whole-record budget packing. Task adapters may replace the default parser/router
without changing the compiler interface.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
import math
import re
from collections import Counter, defaultdict
from typing import Callable, Iterable, Sequence

_TOKEN_RE = re.compile(r"[A-Za-z_][A-Za-z0-9_.:/-]*|[-+]?\d+(?:\.\d+)?")
_ID_RE = re.compile(r"\b(?:[A-Z]{2,}\d+|[A-Z][A-Z0-9_-]{2,}|\d+(?:\.\d+)?)\b")
_SET_RE = re.compile(r"^\s*([A-Za-z_][\w.-]*)\s*=\s*([^;\n]+?)\s*$")
_COPY_RE = re.compile(r"^\s*([A-Za-z_][\w.-]*)\s+(?:copies|copy|takes)\s+([A-Za-z_][\w.-]*)\s*$", re.I)
_EDGE_RE = re.compile(r"^\s*([\w.-]+)\s+-\[([\w.-]+)\]->\s*([\w.-]+)\s*$")
_RELSEQ_RE = re.compile(r"(?:relation|path)\s*[:=]\s*([A-Za-z0-9_.-]+(?:\s*>\s*[A-Za-z0-9_.-]+)*)", re.I)


class Route(str, Enum):
    STATE = "state"
    RELATION = "relation"
    COUNT = "count"
    RAW = "raw"


@dataclass(frozen=True)
class SourceUnit:
    source_id: str
    order: int
    text: str


@dataclass(frozen=True)
class Fact:
    kind: str
    args: tuple[str, ...]
    sources: tuple[str, ...]
    order: int


@dataclass(frozen=True)
class Record:
    record_type: str
    key: str
    value: str
    sources: tuple[str, ...]
    priority: float = 1.0

    def render(self) -> str:
        src = ",".join(self.sources)
        return f"[{self.record_type}] {self.key} = {self.value}  <src:{src}>"


@dataclass
class TOMCConfig:
    evidence_units: int = 128
    neighbor_radius: int = 1
    compiled_fraction: float = 0.42
    max_state_rows: int = 96
    max_count_rows: int = 80
    max_relation_paths: int = 120
    lexical_weight: float = 1.0
    exact_weight: float = 0.8
    operation_weight: float = 0.6
    anchor_weight: float = 0.25
    redundancy_weight: float = 0.30
    token_counter: Callable[[str], int] = lambda s: len(_TOKEN_RE.findall(s))


def lexical_tokens(text: str) -> list[str]:
    return [m.group(0).lower() for m in _TOKEN_RE.finditer(text)]


def segment_lines(history: str) -> list[SourceUnit]:
    lines = [line.strip() for line in history.splitlines() if line.strip()]
    return [SourceUnit(f"u{i+1}", i, line) for i, line in enumerate(lines)]


def _jaccard(a: set[str], b: set[str]) -> float:
    return len(a & b) / max(1, len(a | b))


def _base_score(unit: SourceUnit, query: str, cfg: TOMCConfig) -> float:
    uq = set(lexical_tokens(unit.text))
    qq = set(lexical_tokens(query))
    lexical = len(uq & qq) / max(1, len(qq))
    exact_terms = set(_ID_RE.findall(query))
    exact = sum(1 for t in exact_terms if t in unit.text) / max(1, len(exact_terms)) if exact_terms else 0.0
    low = unit.text.lower()
    operation = float(any(k in low for k in ("=", "changed", "updated", "copies", "->", "assigned", "credential")))
    anchor = float(low.startswith(("schema", "table", "state", "current", "final")))
    return cfg.lexical_weight * lexical + cfg.exact_weight * exact + cfg.operation_weight * operation + cfg.anchor_weight * anchor


def select_evidence(units: Sequence[SourceUnit], query: str, cfg: TOMCConfig) -> list[SourceUnit]:
    """Deterministic MMR-style source selection followed by local expansion."""
    if not units:
        return []
    remaining = list(units)
    base = {u.source_id: _base_score(u, query, cfg) for u in units}
    selected: list[SourceUnit] = []
    selected_sets: list[set[str]] = []
    while remaining and len(selected) < cfg.evidence_units:
        def score(u: SourceUnit) -> tuple[float, int]:
            us = set(lexical_tokens(u.text))
            red = max((_jaccard(us, s) for s in selected_sets), default=0.0)
            return (base[u.source_id] - cfg.redundancy_weight * red, -u.order)
        best = max(remaining, key=score)
        if base[best.source_id] <= 0 and selected:
            break
        selected.append(best)
        selected_sets.append(set(lexical_tokens(best.text)))
        remaining.remove(best)

    idx = {u.order for u in selected}
    for u in list(selected):
        for j in range(max(0, u.order - cfg.neighbor_radius), min(len(units), u.order + cfg.neighbor_radius + 1)):
            idx.add(j)
    return [units[i] for i in sorted(idx)]


def default_route(query: str) -> Route:
    q = query.lower()
    if any(k in q for k in ("current", "final value", "latest value", "ends at", "end at")):
        return Route.STATE
    if any(k in q for k in ("how many", "frequency", "most frequent", "common word", "count")):
        return Route.COUNT
    if any(k in q for k in ("related", "relation", "associated", "credential", "linked", "path", "which account")):
        return Route.RELATION
    return Route.RAW


def parse_default(evidence: Sequence[SourceUnit]) -> list[Fact]:
    facts: list[Fact] = []
    for u in evidence:
        m = _COPY_RE.match(u.text)
        if m:
            facts.append(Fact("COPY", (m.group(1), m.group(2)), (u.source_id,), u.order)); continue
        m = _SET_RE.match(u.text)
        if m:
            facts.append(Fact("SET", (m.group(1), m.group(2).strip()), (u.source_id,), u.order)); continue
        m = _EDGE_RE.match(u.text)
        if m:
            facts.append(Fact("EDGE", (m.group(1), m.group(2), m.group(3)), (u.source_id,), u.order)); continue
    return facts


def compile_state(facts: Sequence[Fact], cfg: TOMCConfig) -> list[Record]:
    state: dict[str, str] = {}
    support: dict[str, tuple[str, ...]] = {}
    for f in sorted(facts, key=lambda x: x.order):
        if f.kind == "SET":
            var, val = f.args
            state[var] = val
            support[var] = f.sources
        elif f.kind == "COPY":
            dst, src = f.args
            state[dst] = state.get(src, "<UNKNOWN>")
            support[dst] = tuple(dict.fromkeys((*support.get(src, ()), *f.sources)))
    rows = [Record("STATE", k, v, support.get(k, ()), 3.0) for k, v in state.items()]
    rows.sort(key=lambda r: r.key)
    return rows[: cfg.max_state_rows]


def relation_labels_from_query(query: str) -> tuple[str, ...]:
    """Read an explicit relation path such as ``relation: assigned_to > credential``.

    Natural-language benchmarks can replace this function with a task adapter that
    returns the required label sequence.
    """
    m = _RELSEQ_RE.search(query)
    if not m:
        return ()
    return tuple(x.strip() for x in m.group(1).split(">") if x.strip())


def compile_relations(facts: Sequence[Fact], relation_labels: Sequence[str], cfg: TOMCConfig) -> list[Record]:
    """Join typed edges along a declared relation-label sequence.

    With no declared sequence, expose direct edges.  With a sequence, preserve every
    witness path up to ``max_relation_paths`` and union source IDs along that path.
    """
    edges = [f for f in facts if f.kind == "EDGE"]
    if not edges:
        return []
    if not relation_labels:
        rows = [Record("EDGE", f"{h} --{rel}--> {t}", "true", f.sources, 2.5)
                for f in edges for h, rel, t in [f.args]]
        rows.sort(key=lambda r: (r.key, r.sources))
        return rows[: cfg.max_relation_paths]

    by_label: dict[str, list[Fact]] = defaultdict(list)
    for f in edges:
        by_label[f.args[1]].append(f)
    for fs in by_label.values():
        fs.sort(key=lambda f: (f.args[0], f.args[2], f.order))

    first = relation_labels[0]
    paths: list[tuple[str, str, tuple[str, ...], tuple[str, ...]]] = []
    # (start, current, labels, sources)
    for f in by_label.get(first, []):
        h, _, t = f.args
        paths.append((h, t, (first,), f.sources))

    for label in relation_labels[1:]:
        nxt: list[tuple[str, str, tuple[str, ...], tuple[str, ...]]] = []
        for start_node, current, labs, srcs in paths:
            for f in by_label.get(label, []):
                h, _, t = f.args
                if h != current:
                    continue
                merged = tuple(dict.fromkeys((*srcs, *f.sources)))
                nxt.append((start_node, t, (*labs, label), merged))
                if len(nxt) >= cfg.max_relation_paths:
                    break
            if len(nxt) >= cfg.max_relation_paths:
                break
        paths = nxt
        if not paths:
            break

    rows = [Record("PATH", start, f"{' > '.join(labs)} => {end}", srcs, 2.5)
            for start, end, labs, srcs in paths]
    rows.sort(key=lambda r: (r.key, r.value, r.sources))
    return rows[: cfg.max_relation_paths]

def compile_counts(evidence: Sequence[SourceUnit], cfg: TOMCConfig) -> list[Record]:
    occ: Counter[str] = Counter()
    sup: Counter[str] = Counter()
    for u in evidence:
        w = lexical_tokens(u.text)
        occ.update(w)
        sup.update(set(w))
    rows = [Record("COUNT", k, f"occ={occ[k]}, support={sup[k]}", (), 1.5) for k in occ]
    rows.sort(key=lambda r: (-occ[r.key], r.key))
    return rows[: cfg.max_count_rows]


def compile_records(route: Route, evidence: Sequence[SourceUnit], query: str, cfg: TOMCConfig,
                    parser: Callable[[Sequence[SourceUnit]], list[Fact]] = parse_default,
                    relation_fn: Callable[[str], Sequence[str]] = relation_labels_from_query) -> list[Record]:
    if route == Route.RAW:
        return []
    facts = parser(evidence)
    if route == Route.STATE:
        return compile_state(facts, cfg)
    if route == Route.RELATION:
        return compile_relations(facts, relation_fn(query), cfg)
    if route == Route.COUNT:
        return compile_counts(evidence, cfg)
    raise ValueError(route)


def _pack_lines(lines: Iterable[str], budget: int, token_counter: Callable[[str], int]) -> str:
    out: list[str] = []
    used = 0
    for line in lines:
        cost = token_counter(line + "\n")
        if used + cost > budget:
            continue
        out.append(line)
        used += cost
    return "\n".join(out)


def pack_memory(records: Sequence[Record], raw: Sequence[SourceUnit], budget: int, cfg: TOMCConfig) -> str:
    compiled_budget = min(budget, max(0, math.floor(cfg.compiled_fraction * budget))) if records else 0
    raw_budget = budget - compiled_budget
    record_lines = [r.render() for r in sorted(records, key=lambda r: (-r.priority, r.record_type, r.key))]
    compiled = _pack_lines(record_lines, compiled_budget, cfg.token_counter)
    raw_lines = [f"[RAW {u.source_id}] {u.text}" for u in raw]
    raw_text = _pack_lines(raw_lines, raw_budget, cfg.token_counter)
    parts = [p for p in (compiled, raw_text) if p]
    memory = "\n".join(parts)
    # Whole-record packing keeps the reference implementation within budget.
    assert cfg.token_counter(memory) <= budget
    return memory


def tomc(history: str, query: str, budget: int, cfg: TOMCConfig | None = None,
         route_fn: Callable[[str], Route] = default_route,
         parser: Callable[[Sequence[SourceUnit]], list[Fact]] = parse_default,
         relation_fn: Callable[[str], Sequence[str]] = relation_labels_from_query) -> str:
    cfg = cfg or TOMCConfig()
    units = segment_lines(history)
    evidence = select_evidence(units, query, cfg)
    route = route_fn(query)
    records = compile_records(route, evidence, query, cfg, parser, relation_fn)
    return pack_memory(records, evidence, budget, cfg)


def amcr_ablation(history: str, query: str, budget: int, cfg: TOMCConfig | None = None) -> str:
    """Selection-only ablation: same source units/selection, no typed compilation."""
    cfg = cfg or TOMCConfig(compiled_fraction=0.0)
    units = segment_lines(history)
    evidence = select_evidence(units, query, cfg)
    return _pack_lines((f"[RAW {u.source_id}] {u.text}" for u in evidence), budget, cfg.token_counter)


if __name__ == "__main__":
    history = "A = 3\nB copies A\nA = 8\nC copies B"
    print(tomc(history, "What is the current final value of A?", 64))
