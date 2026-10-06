"""TOMC2: training-free executable memory compilation for code agents.

TOMC2 is intentionally distinct from the byte-frozen TOMC implementation. Legacy TOMC
compiles structured question-answer context. TOMC2 compiles a long software-agent trace
into an auditable working state that can be reinserted into any API-based agent loop.
"""

from __future__ import annotations

import hashlib
import heapq
import inspect
import io
import os
import re
from collections import Counter
from collections import deque
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Iterable, Sequence

from .types import CompressionOutput
from .utils import approx_token_count, pack_blocks

_FILE_RE = re.compile(
    r"(?<![\w/.-])(?:[A-Za-z0-9_.-]+/)+(?:[A-Za-z0-9_.-]+\.(?:py|js|ts|tsx|jsx|java|go|rs|cpp|cc|c|h|hpp|rb|php|md|toml|yaml|yml|json|sh|sql)|[A-Za-z0-9_.-]+)(?![\w/.-])"
)
_SYMBOL_RE = re.compile(r"\b(?:def|class|function|fn|method)\s+([A-Za-z_][A-Za-z0-9_]*)|\b([A-Za-z_][A-Za-z0-9_]*)\s*\(")
_ERROR_RE = re.compile(
    r"\b(?:AssertionError|TypeError|ValueError|KeyError|IndexError|RuntimeError|ImportError|ModuleNotFoundError|SyntaxError|Traceback|FAILED|ERROR|panic|segmentation fault|exception)\b",
    re.I,
)
_TEST_RE = re.compile(r"\b(?:pytest|python\s+-m\s+pytest|npm\s+test|pnpm\s+test|yarn\s+test|go\s+test|cargo\s+test|mvn\s+test|gradle\s+test|ctest|tox|nox)\b[^\n]{0,260}", re.I)
_ATTEMPT_RE = re.compile(
    r"\b(?:tried|attempted|edited|changed|patched|reverted|rolled back|did not work|still fail(?:ed|ing)?|regression|workaround|hypothesis)\b",
    re.I,
)
_REQUIREMENT_RE = re.compile(r"\b(?:must|should|need(?:s|ed)? to|required|acceptance criteria|expected behavior|goal|task|issue)\b", re.I)
_SUCCESS_RE = re.compile(r"\b(?:passed|fixed|resolved|green|succeeded|working now|no longer fails)\b", re.I)
_COMMAND_RE = re.compile(r"(?:^|[`$>]\s*)(?P<cmd>(?:python|pytest|git|grep|rg|sed|awk|npm|pnpm|yarn|go|cargo|mvn|gradle|make|cmake|docker|bash|sh)\b[^\n`]*)", re.I | re.M)


def _env_int(name: str, default: int) -> int:
    try:
        return int(os.environ.get(name, str(default)))
    except ValueError:
        return default


def _clip_long_line(line: str, max_chars: int) -> str:
    line = line.strip()
    if max_chars <= 0 or len(line) <= max_chars:
        return line
    head = max_chars // 2
    tail = max_chars - head
    return line[:head] + " ... [line clipped] ... " + line[-tail:]


def _prefilter_extreme_trace(context: str, question: str) -> tuple[str, dict[str, object]]:
    """Bound TOMC2 memory use on million-token official benchmark contexts.

    TOMC2 was built for agent traces, but LongBench-v2 contains multi-million-token code
    repository contexts. This streaming prefilter scans the complete context and keeps a
    bounded set of head/tail/query/code/error/test/attempt lines before the structured
    compiler runs.
    """

    min_chars = _env_int("COM_TOMC2_PREFILTER_MIN_CHARS", 2_000_000)
    if len(context) < min_chars:
        return context, {"enabled": False, "reason": "below_char_threshold", "min_chars": min_chars}

    max_units = max(512, _env_int("COM_TOMC2_PREFILTER_MAX_UNITS", 12_000))
    head_units = max(32, _env_int("COM_TOMC2_PREFILTER_HEAD_UNITS", 384))
    tail_units = max(32, _env_int("COM_TOMC2_PREFILTER_TAIL_UNITS", 384))
    signal_units = max(128, _env_int("COM_TOMC2_PREFILTER_SIGNAL_UNITS", 2_048))
    max_line_chars = max(256, _env_int("COM_TOMC2_PREFILTER_MAX_LINE_CHARS", 2_400))
    reserved = min(max_units - 1, head_units + tail_units + signal_units)
    top_units = max(128, max_units - reserved)

    q_terms = _question_words(question)
    if len(q_terms) > 80:
        q_terms = set(sorted(q_terms, key=len, reverse=True)[:80])

    head: list[tuple[int, str]] = []
    tail: deque[tuple[int, str]] = deque(maxlen=tail_units)
    signals: list[tuple[int, str]] = []
    top_heap: list[tuple[float, int, int, str]] = []
    total_lines = 0
    nonempty_lines = 0
    signal_seen = 0

    for idx, raw_line in enumerate(io.StringIO(context)):
        total_lines += 1
        stripped = raw_line.strip()
        if not stripped:
            continue
        nonempty_lines += 1
        line = _clip_long_line(stripped, max_line_chars)
        if len(head) < head_units:
            head.append((idx, line))
        tail.append((idx, line))
        lower = line.lower()
        term_hits = sum(1 for term in q_terms if term in lower)
        file_hit = bool(_FILE_RE.search(line))
        error_hit = bool(_ERROR_RE.search(line))
        test_hit = bool(_TEST_RE.search(line))
        attempt_hit = bool(_ATTEMPT_RE.search(line))
        requirement_hit = bool(_REQUIREMENT_RE.search(line))
        code_hit = bool(re.search(r"\b(?:class|def|function|method|module|import|return|api|schema|config|solver|repository)\b", lower))
        score = float(term_hits * 8)
        score += 2.0 if file_hit else 0.0
        score += 2.0 if error_hit else 0.0
        score += 1.5 if test_hit else 0.0
        score += 1.0 if attempt_hit else 0.0
        score += 1.0 if requirement_hit else 0.0
        score += 0.75 if code_hit else 0.0
        if score > 0:
            signal_seen += 1
            if len(signals) < signal_units and (file_hit or error_hit or test_hit or attempt_hit or requirement_hit or code_hit):
                signals.append((idx, line))
            item = (score, -idx, idx, line)
            if len(top_heap) < top_units:
                heapq.heappush(top_heap, item)
            elif item > top_heap[0]:
                heapq.heapreplace(top_heap, item)

    merged: dict[int, str] = {}
    for idx, line in head:
        merged.setdefault(idx, f"[orig_line={idx} source=head] {line}")
    for idx, line in signals:
        merged.setdefault(idx, f"[orig_line={idx} source=signal] {line}")
    for score, _, idx, line in sorted(top_heap, key=lambda x: (-x[0], x[2])):
        merged.setdefault(idx, f"[orig_line={idx} source=query_top score={score:.2f}] {line}")
    for idx, line in tail:
        merged.setdefault(idx, f"[orig_line={idx} source=tail] {line}")

    selected = sorted(merged.items())
    prefiltered = "\n".join(line for _, line in selected)
    return prefiltered, {
        "enabled": True,
        "strategy": "streaming_head_tail_query_code_signal_lines",
        "original_chars": len(context),
        "original_tokens_approx": approx_token_count(context),
        "total_lines": total_lines,
        "nonempty_lines": nonempty_lines,
        "signal_seen": signal_seen,
        "selected_units": len(selected),
        "selected_tokens_approx": approx_token_count(prefiltered),
        "min_chars": min_chars,
        "max_units": max_units,
        "head_units": head_units,
        "tail_units": tail_units,
        "signal_units": signal_units,
        "top_units": top_units,
        "max_line_chars": max_line_chars,
        "query_terms_used": sorted(q_terms)[:80],
    }


@dataclass(frozen=True)
class TOMC2Config:
    recent_raw_fraction: float = 0.30
    max_goal_rows: int = 24
    max_repo_rows: int = 100
    max_error_rows: int = 80
    max_attempt_rows: int = 80
    max_fact_rows: int = 100
    max_verifier_rows: int = 30
    include_attempt_ledger: bool = True
    include_test_ledger: bool = True
    include_verifiers: bool = True
    include_provenance: bool = True
    include_next_action_prior: bool = True
    include_recent_raw: bool = True


@dataclass(frozen=True)
class TraceUnit:
    idx: int
    text: str


def _implementation_sha() -> str:
    return hashlib.sha256(Path(inspect.getfile(TOMC2Config)).read_bytes()).hexdigest()


def _units(text: str) -> list[TraceUnit]:
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    if len(lines) < 4:
        lines = [x.strip() for x in re.split(r"(?<=[.!?])\s+", text) if x.strip()]
    return [TraceUnit(i, line) for i, line in enumerate(lines)]


def _source_prefix(unit: TraceUnit, include: bool) -> str:
    return f"source=u{unit.idx}\t" if include else ""


def _dedupe(items: Iterable[str]) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for item in items:
        key = item.strip()
        if not key or key in seen:
            continue
        seen.add(key)
        out.append(key)
    return out


def _question_words(question: str) -> set[str]:
    return {w.lower() for w in re.findall(r"[A-Za-z_][A-Za-z0-9_./:-]*", question) if len(w) > 2}


def _relevance(text: str, question: str) -> float:
    q = _question_words(question)
    t = _question_words(text)
    overlap = len(q & t)
    score = overlap * 3.0 + overlap / max(1, len(t))
    if _ERROR_RE.search(text):
        score += 2.0
    if _TEST_RE.search(text):
        score += 1.5
    if _FILE_RE.search(text):
        score += 0.7
    if _ATTEMPT_RE.search(text):
        score += 0.5
    return score


class TOMC2AgentCompiler:
    name = "tomc2_agent"

    def __init__(self, config: TOMC2Config | None = None, *, name: str | None = None):
        self.config = config or TOMC2Config()
        if name:
            self.name = name

    def compress(self, context: str, question: str, budget_tokens: int) -> CompressionOutput:
        work_context, prefilter_diag = _prefilter_extreme_trace(context, question)
        units = _units(work_context)
        cfg = self.config
        symbolic_budget = budget_tokens
        if cfg.include_recent_raw:
            symbolic_budget = max(64, int(budget_tokens * (1.0 - cfg.recent_raw_fraction)))
        blocks: list[str] = [self._header(question)]
        blocks.append(self._goals(units, question))
        blocks.append(self._repo_map(units))
        if cfg.include_test_ledger:
            blocks.append(self._test_error_ledger(units))
        if cfg.include_attempt_ledger:
            blocks.append(self._attempt_ledger(units))
        blocks.append(self._facts(units, question))
        if cfg.include_verifiers:
            blocks.append(self._verifiers(units))
        if cfg.include_next_action_prior:
            blocks.append(self._next_action(units, question))
        compiled = pack_blocks(blocks, symbolic_budget)
        final_blocks = [compiled]
        if cfg.include_recent_raw:
            raw_budget = max(1, budget_tokens - approx_token_count(compiled))
            final_blocks.append(self._recent_raw(units, raw_budget))
        text = pack_blocks(final_blocks, budget_tokens)
        diagnostics = {
            "units": len(units),
            "file_count": len(set(_FILE_RE.findall(work_context))),
            "error_rows": sum(bool(_ERROR_RE.search(u.text)) for u in units),
            "attempt_rows": sum(bool(_ATTEMPT_RE.search(u.text)) for u in units),
            "verifier_rows": len(_dedupe(m.group(0).strip() for u in units for m in _TEST_RE.finditer(u.text))),
            "compiled_tokens": approx_token_count(text),
            "config": cfg.__dict__,
            "extreme_context_prefilter": prefilter_diag,
        }
        return CompressionOutput(
            text=text,
            method=self.name,
            budget_tokens=budget_tokens,
            approx_tokens=approx_token_count(text),
            diagnostics=diagnostics,
            implementation_sha256=_implementation_sha(),
        )

    def _header(self, question: str) -> str:
        return (
            "EXECUTABLE AGENT MEMORY\n"
            "memory_schema: TOMC2/v2\n"
            f"goal_or_query: {question}\n"
            "policy: Preserve verified state, failed attempts, tests, source locations, and the next check. "
            "Do not repeat an attempt marked failed without new evidence."
        )

    def _goals(self, units: Sequence[TraceUnit], question: str) -> str:
        rows = [f"- explicit_query: {question}"]
        candidates = [u for u in units if _REQUIREMENT_RE.search(u.text)]
        candidates.sort(key=lambda u: (-_relevance(u.text, question), u.idx))
        for u in candidates[: self.config.max_goal_rows]:
            rows.append(f"- {_source_prefix(u, self.config.include_provenance)}{u.text[:700]}")
        return "GOAL / ACCEPTANCE CRITERIA\n" + "\n".join(rows)

    def _repo_map(self, units: Sequence[TraceUnit]) -> str:
        file_counts: Counter[str] = Counter()
        symbol_counts: Counter[str] = Counter()
        source_examples: dict[str, int] = {}
        for u in units:
            for path in _FILE_RE.findall(u.text):
                file_counts[path] += 1
                source_examples.setdefault(path, u.idx)
            for match in _SYMBOL_RE.finditer(u.text):
                symbol = match.group(1) or match.group(2)
                if symbol and len(symbol) > 2:
                    symbol_counts[symbol] += 1
        rows = ["files:"]
        for path, count in file_counts.most_common(self.config.max_repo_rows // 2):
            src = f" source=u{source_examples[path]}" if self.config.include_provenance else ""
            rows.append(f"- {path} mentions={count}{src}")
        rows.append("symbols:")
        rows.extend(f"- {symbol} mentions={count}" for symbol, count in symbol_counts.most_common(self.config.max_repo_rows // 2))
        if len(rows) == 2:
            rows.append("- no_explicit_repo_entities_detected")
        return "REPOSITORY / SYMBOL STATE\n" + "\n".join(rows)

    def _test_error_ledger(self, units: Sequence[TraceUnit]) -> str:
        failed: list[str] = []
        passed: list[str] = []
        for u in units:
            if _ERROR_RE.search(u.text) or re.search(r"\b(?:fail(?:ed|ing)?|red test)\b", u.text, re.I):
                failed.append(f"- {_source_prefix(u, self.config.include_provenance)}{u.text[:900]}")
            elif _SUCCESS_RE.search(u.text) and (_TEST_RE.search(u.text) or "test" in u.text.lower()):
                passed.append(f"- {_source_prefix(u, self.config.include_provenance)}{u.text[:700]}")
        rows = ["failing_or_error_observations:"] + failed[-self.config.max_error_rows :]
        rows += ["passing_or_resolved_observations:"] + passed[-max(10, self.config.max_error_rows // 3) :]
        if not failed and not passed:
            rows.append("- no_test_or_error_state_detected")
        return "TEST / ERROR LEDGER\n" + "\n".join(rows)

    def _attempt_ledger(self, units: Sequence[TraceUnit]) -> str:
        rows: list[str] = []
        for u in units:
            if _ATTEMPT_RE.search(u.text):
                outcome = "failed_or_uncertain"
                if _SUCCESS_RE.search(u.text):
                    outcome = "successful_or_resolved"
                elif re.search(r"\b(?:revert|rolled back|did not work|still fail)\b", u.text, re.I):
                    outcome = "failed"
                rows.append(f"- outcome={outcome}\t{_source_prefix(u, self.config.include_provenance)}{u.text[:900]}")
        if not rows:
            rows = ["- no_explicit_attempts_detected"]
        return "ATTEMPT LEDGER\n" + "\n".join(rows[-self.config.max_attempt_rows :])

    def _facts(self, units: Sequence[TraceUnit], question: str) -> str:
        ranked = sorted(units, key=lambda u: (-_relevance(u.text, question), u.idx))
        rows: list[str] = []
        for u in ranked:
            score = _relevance(u.text, question)
            if score <= 0:
                continue
            rows.append(f"- score={score:.2f}\t{_source_prefix(u, self.config.include_provenance)}{u.text[:900]}")
            if len(rows) >= self.config.max_fact_rows:
                break
        if not rows:
            rows = ["- no_query_relevant_fact_detected"]
        return "RELEVANT FACTS\n" + "\n".join(rows)

    def _verifiers(self, units: Sequence[TraceUnit]) -> str:
        commands: list[str] = []
        for u in units:
            commands.extend(m.group(0).strip().rstrip(".;") for m in _TEST_RE.finditer(u.text))
            commands.extend(m.group("cmd").strip().rstrip(".;") for m in _COMMAND_RE.finditer(u.text))
        commands = _dedupe(commands)
        if not commands:
            commands = [
                "run the smallest directly affected test first",
                "run the repository's standard test command after the focused test passes",
                "inspect git diff before submission",
            ]
        return "VERIFIER COMMANDS\n" + "\n".join(f"- {cmd}" for cmd in commands[: self.config.max_verifier_rows])

    def _next_action(self, units: Sequence[TraceUnit], question: str) -> str:
        paths = Counter(path for u in units for path in _FILE_RE.findall(u.text))
        failing = [u for u in units if _ERROR_RE.search(u.text) or "fail" in u.text.lower()]
        attempts = [u for u in units if _ATTEMPT_RE.search(u.text)]
        rows = ["- inspect the highest-provenance failing observation before editing"]
        if paths:
            rows.append(f"- likely_first_file_to_inspect: {paths.most_common(1)[0][0]}")
        if failing:
            rows.append(f"- latest_failure_source: u{failing[-1].idx}")
        if attempts:
            rows.append(f"- compare against latest_attempt_source: u{attempts[-1].idx}")
        rows.append("- after a minimal edit, run the most focused verifier listed above")
        return "NEXT-ACTION PRIOR\n" + "\n".join(rows)

    def _recent_raw(self, units: Sequence[TraceUnit], budget_tokens: int) -> str:
        rows: list[str] = []
        used = 0
        for u in reversed(units):
            row = f"u{u.idx}: {u.text}"
            count = approx_token_count(row)
            if rows and used + count > budget_tokens:
                break
            rows.append(row)
            used += count
        rows.reverse()
        return "RECENT RAW TRACE BACKUP\n" + "\n".join(rows)


class TOMC2NoAttemptCompiler(TOMC2AgentCompiler):
    def __init__(self):
        super().__init__(replace(TOMC2Config(), include_attempt_ledger=False), name="tomc2_no_attempt")


class TOMC2NoVerifierCompiler(TOMC2AgentCompiler):
    def __init__(self):
        super().__init__(replace(TOMC2Config(), include_verifiers=False), name="tomc2_no_verifier")


class TOMC2NoProvenanceCompiler(TOMC2AgentCompiler):
    def __init__(self):
        super().__init__(replace(TOMC2Config(), include_provenance=False), name="tomc2_no_provenance")


class TOMC2CompilerOnly(TOMC2AgentCompiler):
    def __init__(self):
        super().__init__(replace(TOMC2Config(), include_recent_raw=False), name="tomc2_compiler_only")


class TOMC2HybridCompiler:
    """Frozen automatic router: executable agent memory for software traces, legacy TOMC otherwise."""

    name = "tomc2_hybrid"

    def compress(self, context: str, question: str, budget_tokens: int) -> CompressionOutput:
        code_signals = sum(
            [
                bool(_FILE_RE.search(context)),
                bool(_ERROR_RE.search(context)),
                bool(_TEST_RE.search(context)),
                bool(_ATTEMPT_RE.search(context)),
                bool(re.search(r"\b(?:repository|codebase|patch|commit|function|class)\b", context, re.I)),
            ]
        )
        if code_signals >= 2:
            result = TOMC2AgentCompiler(name=self.name).compress(context, question, budget_tokens)
            result.diagnostics["hybrid_route"] = "tomc2_agent"
            return result
        from .legacy import LegacyMethodAdapter

        legacy = LegacyMethodAdapter("tomc_router").compress(context, question, budget_tokens)
        return CompressionOutput(
            text=legacy.text,
            method=self.name,
            budget_tokens=legacy.budget_tokens,
            approx_tokens=legacy.approx_tokens,
            selected_indices=legacy.selected_indices,
            diagnostics={**legacy.diagnostics, "hybrid_route": "legacy_tomc_router"},
            implementation_sha256=_implementation_sha(),
        )
