"""Audit the 2026-10-05 Windows Codex retention run and export its sanitized report.

This standard-library helper makes no model requests and does not read personal
configuration. This audit is specific to the recorded Windows desktop 0.160.0,
Python 3.11.9, preview.4, gpt-6.1-sol/ultra fixture; its provenance constants must
not be reused to label a different host or future run. It requires all nine
cases, four answering conditions, and saved prompts beside results.json.
cl100k_base counts are descriptive, not the Codex provider's tokenizer or usage.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
import runpy
from datetime import datetime, timezone
from pathlib import Path
from statistics import mean

CONDITIONS = ("full", "40", "60", "80")
LENGTHS = ("10k", "20k", "40k")
SEEDS = (11, 23, 37)
ALLOWED_ITEMS = {"userMessage", "reasoning", "agentMessage"}
USAGE_FIELDS = (
    "inputTokens",
    "cachedInputTokens",
    "cacheWriteInputTokens",
    "outputTokens",
    "reasoningOutputTokens",
    "totalTokens",
)
LEXICAL = re.compile(r"[\u3400-\u9fff]|[^\W_]+(?:_[^\W_]+)*|[^\w\s]|_", re.UNICODE)


def require(condition: bool, message: str) -> None:
    """Fail with a bounded audit message rather than printing model/private data."""
    if not condition:
        raise ValueError(message)


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def norm(value: object) -> str:
    return re.sub(r"[^a-z0-9]", "", str(value).lower().replace(" at ", " "))


def page_cap_matches(actual: object, expected: str) -> bool:
    """Match a cap value or recognized cap wording; reject lists, negation and units."""
    if not isinstance(actual, str):
        return False
    numbers = re.findall(r"\d+", expected)
    if len(numbers) != 1:
        return False
    number = re.escape(numbers[0])
    patterns = (
        number,
        rf"{number}\s*pages?",
        rf"(?:under|at\s+most|up\s+to|max(?:imum)?(?:\s+of)?|no\s+more\s+than)"
        rf"\s+{number}\s*pages?",
        rf"{number}\s*pages?\s+(?:maximum|max|at\s+most)",
    )
    text = actual.strip().lower()
    return any(re.fullmatch(pattern + r"\.?", text) is not None for pattern in patterns)


def grade_answer(answer: str, expected: dict[str, str]) -> dict:
    """Check five current values and retain the earlier Claude-style comparison."""
    match = re.search(r"\{.*\}", answer, re.S)
    try:
        got = json.loads(match[0]) if match else {}
    except (ValueError, TypeError):
        got = {}
    if not isinstance(got, dict):
        got = {}
    checked, legacy = {}, {}
    for key, value in expected.items():
        actual = got.get(key)
        if key == "page_limit":
            checked[key] = page_cap_matches(actual, value)
            legacy[key] = re.findall(r"\d+", value)[0] in re.findall(r"\d+", str(actual))
        else:
            checked[key] = isinstance(actual, str) and norm(actual) == norm(value)
            legacy[key] = norm(value) in norm(actual)
    return {
        "got": got,
        "value_marks": checked,
        "value_correct": sum(checked.values()),
        "claude_legacy_marks": legacy,
        "claude_legacy_correct": sum(legacy.values()),
        "required_values": len(expected),
    }


def checked_usage(raw: dict, label: str) -> dict[str, int]:
    require(isinstance(raw, dict), f"{label}: missing usage object")
    counts = {}
    for field in USAGE_FIELDS:
        value = raw.get(field, 0 if field == "cacheWriteInputTokens" else None)
        require(type(value) is int and value >= 0, f"{label}: invalid {field}")
        counts[field] = value
    require(
        counts["cachedInputTokens"] + counts["cacheWriteInputTokens"] <= counts["inputTokens"],
        f"{label}: overlapping/excess cached input accounting",
    )
    require(
        counts["reasoningOutputTokens"] <= counts["outputTokens"],
        f"{label}: reasoning exceeds output accounting",
    )
    require(
        counts["totalTokens"] == counts["inputTokens"] + counts["outputTokens"],
        f"{label}: total accounting mismatch",
    )
    return counts


def descriptive_summary(cases: dict, keys: list[str]) -> dict:
    """Keep mean counts, equal-case paired changes and ratios of means distinct."""
    full_inputs = [cases[key]["runs"]["full"]["provider_usage"]["inputTokens"] for key in keys]
    summaries = {}
    for condition in CONDITIONS:
        rows = [cases[key]["runs"][condition] for key in keys]
        usages = [row["provider_usage"] for row in rows]
        questions = sum(row["regraded"]["required_values"] for row in rows)
        correct = sum(row["regraded"]["value_correct"] for row in rows)
        legacy_correct = sum(row["regraded"]["claude_legacy_correct"] for row in rows)
        input_mean = mean(u["inputTokens"] for u in usages)
        pairs = [1 - u["inputTokens"] / reference for u, reference in zip(usages, full_inputs)]
        summaries[condition] = {
            "case_count": len(keys),
            "question_count": questions,
            "checked_values_correct": correct,
            "checked_value_accuracy_pct": 100 * correct / questions,
            "claude_legacy_correct": legacy_correct,
            "claude_legacy_accuracy_pct": 100 * legacy_correct / questions,
            "mean_provider_usage": {
                field: mean(u[field] for u in usages) for field in USAGE_FIELDS
            },
            "equal_case_mean_paired_input_decrease_pct": 100 * mean(pairs),
            "input_decrease_from_ratio_of_means_pct": 100 * (1 - input_mean / mean(full_inputs)),
            "paired_input_decrease_range_pct": [100 * min(pairs), 100 * max(pairs)],
            "mean_actual_lexical_evidence_retention_pct": mean(
                row["actual_lexical_evidence_retention_pct"] for row in rows
            ),
            "mean_cl100k_user_prompt_tokens_descriptive": mean(
                row["user_prompt_cl100k_tokens"] for row in rows
            ),
            "mean_provider_minus_cl100k_user_prompt_residual": mean(
                row["provider_minus_cl100k_user_prompt_residual"] for row in rows
            ),
            "mean_observed_duration_seconds": mean(row["duration_seconds"] for row in rows),
        }
    return {"case_keys": keys, "conditions": summaries}


def audit_and_report(results_path: Path, cases_path: Path) -> dict:
    raw_results, raw_cases = results_path.read_bytes(), cases_path.read_bytes()
    results, corpus = json.loads(raw_results), json.loads(raw_cases)
    expected_keys = {f"s{seed}-{length}" for seed in SEEDS for length in LENGTHS}
    require(set(corpus["cases"]) == expected_keys, "Expected all nine synthetic source cases")
    require(set(results["cases"]) == expected_keys, "All nine cases must finish before export")
    require(
        results["corpus_sha256"] == digest(raw_cases), "Corpus hash changed across resumed runs"
    )
    require(results["task"] == corpus["task"], "Resumed task mismatch")
    require(results["questions"] == corpus["questions"], "Resumed questions mismatch")
    require(results["conditions"] == list(CONDITIONS), "Condition definitions changed")
    require(results["personal_config_unchanged"] is True, "Personal configuration audit failed")
    require(bool(results.get("finished_utc")), "Runner must finish before export")
    require(results["profile"]["model"] == "gpt-6.1-sol", "Requested original model changed")
    require(results["profile"]["provider"] == "openai", "Requested original provider changed")
    require(results["profile"]["effort"] == "ultra", "Requested original reasoning effort changed")
    require(results["config_overrides"] == [], "Recorded configuration overrides changed")
    require(
        results["started_utc"].startswith("2026-10-05")
        and results["finished_utc"].startswith("2026-10-05"),
        "This helper's provenance is specific to the 2026-10-05 recorded run",
    )
    require(len(corpus["questions"]) == 5, "Expected five current-value questions")
    prompt_prefix = (
        "Reply with only a JSON object with the keys "
        + ", ".join(corpus["questions"])
        + ", each holding the current value as a short string.\n\n"
        + corpus["task"]
        + "\n\nEvidence:\n"
    )
    clean_cases = {}
    for key in sorted(expected_keys):
        source, recorded = corpus["cases"][key], results["cases"][key]
        history = source["history"]
        history_hash = digest(history.encode("utf-8"))
        lexical_tokens = len(LEXICAL.findall(history))
        require(recorded["history_sha256"] == history_hash, f"{key}: resumed history mismatch")
        require(source["history_sha256"] == history_hash, f"{key}: source history hash mismatch")
        require(
            recorded["expected"] == source["expected"], f"{key}: resumed expected-values mismatch"
        )
        require(
            set(source["expected"]) == set(corpus["questions"]), f"{key}: expected keys mismatch"
        )
        require(recorded["seed"] == source["seed"], f"{key}: seed mismatch")
        require(recorded["length"] == source["length"], f"{key}: length mismatch")
        require(recorded["history_characters"] == len(history), f"{key}: history length mismatch")
        require(
            recorded["history_lexical_tokens"] == lexical_tokens, f"{key}: lexical count mismatch"
        )
        require(set(recorded["runs"]) == set(CONDITIONS), f"{key}: all four conditions must finish")
        clean_runs = {}
        for condition in CONDITIONS:
            row, label = recorded["runs"][condition], f"{key}/{condition}"
            require(row["status"] == "completed", f"{label}: answering turn incomplete")
            require(set(row["item_types"]) <= ALLOWED_ITEMS, f"{label}: observed non-answer item")
            require("userMessage" in row["item_types"], f"{label}: missing user-message telemetry")
            require("agentMessage" in row["item_types"], f"{label}: missing answer telemetry")
            require(bool(row["usage_updates"]), f"{label}: missing usage telemetry")
            snapshots = []
            for snapshot in row["usage_updates"]:
                require(
                    set(snapshot) <= {"last", "total", "modelContextWindow"},
                    f"{label}: unexpected raw usage metadata",
                )
                for breakdown in (snapshot["last"], snapshot["total"]):
                    require(
                        set(breakdown) <= set(USAGE_FIELDS),
                        f"{label}: unexpected raw usage field",
                    )
                last = checked_usage(snapshot["last"], label)
                total = checked_usage(snapshot["total"], label)
                snapshots.append({"last": last, "total": total})
            final = snapshots[-1]
            require(final["last"] == final["total"], f"{label}: extra-response usage")
            usage = checked_usage(row["provider_usage"], label)
            require(usage == final["total"], f"{label}: saved final-usage mismatch")
            prompt_path = results_path.parent / f"{key}-{condition}-prompt.txt"
            prompt = prompt_path.read_text(encoding="utf-8")
            require(prompt.startswith(prompt_prefix), f"{label}: answering envelope mismatch")
            evidence = prompt[len(prompt_prefix) :]
            require(
                digest(evidence.encode()) == row["evidence_sha256"],
                f"{label}: evidence hash mismatch",
            )
            actual_tokens = len(LEXICAL.findall(evidence))
            header_counts = {
                kind: len(re.findall(r"^\[" + kind + r"(?:\]| )", evidence, re.M))
                for kind in ("STATE", "REL", "COUNT", "RAW")
            }
            if condition == "full":
                require(evidence == history, f"{label}: full-history evidence changed")
                require(row["budget"] is None, f"{label}: full-history budget changed")
                require(row["selected_method"] == "full_history", f"{label}: reference changed")
            else:
                require(
                    row["input_estimated_tokens"] == lexical_tokens,
                    f"{label}: input-count mismatch",
                )
                require(
                    row["memory_estimated_tokens"] == actual_tokens,
                    f"{label}: memory-count mismatch",
                )
                budget = (
                    max(1024, math.ceil(lexical_tokens * 0.8))
                    if condition == "80"
                    else int(lexical_tokens * int(condition) / 100)
                )
                require(row["budget"] == budget, f"{label}: installed budget-formula mismatch")
                require(actual_tokens <= budget, f"{label}: budget overflow")
            require(
                row["budget_omitted"] is (condition == "80"), f"{label}: omitted-budget mismatch"
            )
            require(isinstance(row["answer"], str), f"{label}: invalid answer type")
            regraded = grade_answer(row["answer"], source["expected"])
            require(
                regraded["claude_legacy_correct"] == row["grading"]["claude_legacy_correct"],
                f"{label}: previous legacy grading changed",
            )
            descriptive_tokens = row["user_prompt_cl100k_tokens"]
            require(
                type(descriptive_tokens) is int and descriptive_tokens > 0,
                f"{label}: descriptive count missing",
            )
            clean_runs[condition] = {
                "status": "completed",
                "budget": row["budget"],
                "budget_omitted": row["budget_omitted"],
                "selected_method": row["selected_method"],
                "prompt_sha256": digest(prompt.encode()),
                "evidence_sha256": row["evidence_sha256"],
                "evidence_lexical_tokens": actual_tokens,
                "retained_evidence_header_counts": header_counts,
                "actual_lexical_evidence_retention_pct": 100 * actual_tokens / lexical_tokens,
                "evidence_cl100k_tokens": row["evidence_cl100k_tokens"],
                "user_prompt_cl100k_tokens": descriptive_tokens,
                "provider_minus_cl100k_user_prompt_residual": usage["inputTokens"]
                - descriptive_tokens,
                "provider_usage": usage,
                "raw_usage_updates": row["usage_updates"],
                "item_types": row["item_types"],
                "answer": row["answer"],
                "original_grading": row["grading"],
                "regraded_value_matches": regraded["value_marks"],
                "checked_value_score": regraded["value_correct"],
                "regraded": regraded,
                "duration_seconds": row["duration_seconds"],
            }
        full_input = clean_runs["full"]["provider_usage"]["inputTokens"]
        for row in clean_runs.values():
            row["paired_provider_input_decrease_pct"] = 100 * (
                1 - row["provider_usage"]["inputTokens"] / full_input
            )
        clean_cases[key] = {
            "seed": source["seed"],
            "length": source["length"],
            "history_sha256": history_hash,
            "history_characters": len(history),
            "history_lexical_tokens": lexical_tokens,
            "history_cl100k_tokens": recorded["history_cl100k_tokens"],
            "expected": source["expected"],
            "runs": clean_runs,
        }
    keys = sorted(clean_cases)
    source_root = Path(__file__).resolve().parents[2]
    cached_root = Path.home() / ".codex/plugins/cache/tomc-local/tomc-memory/0.1.0/src/tomc"
    runtime_hashes = {}
    for filename in ("easy.py", "mcp_server.py", "compiler.py"):
        source_data = (source_root / "src/tomc" / filename).read_bytes()
        cached_data = (cached_root / filename).read_bytes()
        require(
            source_data == cached_data,
            f"Installed {filename} differs from tested repository source",
        )
        runtime_hashes[filename] = digest(source_data)
    return {
        "schema_version": 1,
        "status": "complete and audited",
        "exported_utc": datetime.now(timezone.utc).isoformat(),
        "started_utc": results["started_utc"],
        "finished_utc": results["finished_utc"],
        "provenance": {
            "results_sha256": digest(raw_results),
            "corpus_sha256": digest(raw_cases),
            "report_helper_sha256": digest(Path(__file__).read_bytes()),
            "generator_design": "Three synthetic seeds at three nested history lengths; five current-value questions per case",
        },
        "profile": results["profile"],
        "config_overrides": results["config_overrides"],
        "measurement_context": {
            "platform": "Windows desktop",
            "codex_cli_version": "0.160.0",
            "python_version": "3.11.9",
            "assistant_preview_release": "v0.1.0-assistant-preview.4",
            "repository_source_commit": "ad89208dad0528f1a10235e7b572602e2f5f15c2",
            "installed_sources_byte_identical_to_repository": True,
            "runtime_source_sha256": runtime_hashes,
            "preparation": "Installed native MCP tool invoked outside the answering model; no model call or notebook operation",
            "answering": "Original model/provider/effort with one fresh ephemeral answering turn per condition",
            "equal_temporary_thread_controls": {
                "approvalPolicy": "never",
                "sandbox": "read-only",
                "environments": [],
                "runtimeWorkspaceRoots": [],
                "developerInstructions": "Same synthetic-benchmark instruction for all conditions",
            },
        },
        "personal_config_unchanged": True,
        "model_answering_turns": 36,
        "task": corpus["task"],
        "questions": corpus["questions"],
        "cases": clean_cases,
        "per_length": {
            length: descriptive_summary(
                clean_cases, [key for key in keys if clean_cases[key]["length"] == length]
            )
            for length in LENGTHS
        },
        "overall": descriptive_summary(clean_cases, keys),
        "limitations": [
            "One observed tool-free answering turn per condition; telemetry cannot rule out hidden transport retries.",
            "Preparation is an external zero-model MCP call; this is request-evidence replacement, not an entire in-chat compression workflow.",
            "Provider input includes Codex host instructions and tools. cl100k_base is a descriptive counter and is not asserted to be the provider tokenizer.",
            "Provider minus cl100k prompt counts are residuals combining host overhead and counting differences; they are not exact system-token measurements.",
            "Three seeds and nested lengths are correlated synthetic cases, not independent real user projects or a general coding benchmark.",
            "Value scoring checks strings and recognized cap paraphrases; it does not evaluate the distinction between inclusive and exclusive page limits.",
            "The natural-language histories use the tomc_raw route and retain RAW source blocks without STATE/REL/COUNT records. This run does not independently validate typed-record compilation.",
            "The earlier substring-based Claude score is retained for transparency, alongside checked current-value scoring.",
            "Budget percentages refer to lexical memory caps. Achieved retention and complete provider-input changes are reported separately.",
            "Concurrent answering and cache state can affect duration and cached-input counts. No cash-cost or speedup claim follows from this run.",
        ],
    }


def saved_matches(actual: object, expected: object, label: str) -> None:
    """Check saved derived fields, allowing only tiny floating-point differences."""
    if isinstance(expected, dict):
        require(isinstance(actual, dict) and set(actual) == set(expected), f"{label}: keys differ")
        for key, value in expected.items():
            saved_matches(actual[key], value, f"{label}/{key}")
    elif isinstance(expected, list):
        require(
            isinstance(actual, list) and len(actual) == len(expected), f"{label}: length differs"
        )
        for index, value in enumerate(expected):
            saved_matches(actual[index], value, f"{label}/{index}")
    elif isinstance(expected, float):
        require(
            type(actual) in (int, float)
            and math.isclose(actual, expected, rel_tol=0, abs_tol=1e-9),
            f"{label}: number differs",
        )
    else:
        require(type(actual) is type(expected) and actual == expected, f"{label}: value differs")


def verify_published(path: Path) -> dict:
    """Verify saved synthetic answers and usage aggregates without rerunning a host."""
    report = json.loads(path.read_bytes())
    generator = runpy.run_path(str(Path(__file__).with_name("codex_retention_cases.py")))
    corpus = generator["generate_cases"]()
    keys = sorted(corpus["cases"])
    require(
        report["schema_version"] == 1 and report["status"] == "complete and audited",
        "Unsupported published status/schema",
    )
    require(
        report["model_answering_turns"] == 36 and report["personal_config_unchanged"] is True,
        "Recorded acceptance labels differ",
    )
    saved_matches(
        report["profile"],
        {"model": "gpt-6.1-sol", "provider": "openai", "effort": "ultra"},
        "profile",
    )
    require(report["config_overrides"] == [], "Recorded override labels differ")
    for field in ("started_utc", "finished_utc"):
        stamp = datetime.fromisoformat(report[field])
        require(
            stamp.tzinfo is not None
            and stamp.astimezone(timezone.utc).date().isoformat() == "2026-10-05",
            f"{field}: recorded run date differs",
        )
    require(
        datetime.fromisoformat(report["finished_utc"])
        >= datetime.fromisoformat(report["started_utc"]),
        "Recorded dates out of order",
    )
    context = report["measurement_context"]
    for field, value in {
        "platform": "Windows desktop",
        "codex_cli_version": "0.160.0",
        "python_version": "3.11.9",
        "assistant_preview_release": "v0.1.0-assistant-preview.4",
        "repository_source_commit": "ad89208dad0528f1a10235e7b572602e2f5f15c2",
        "installed_sources_byte_identical_to_repository": True,
    }.items():
        require(context[field] == value, f"{field}: recorded provenance label differs")
    provenance = report["provenance"]
    for field in ("results_sha256", "corpus_sha256", "report_helper_sha256"):
        require(
            re.fullmatch(r"[0-9a-f]{64}", provenance[field]) is not None, f"{field}: invalid digest"
        )
    encoded = (json.dumps(corpus, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    require(provenance["corpus_sha256"] == digest(encoded), "Generated corpus digest differs")
    require(
        provenance["report_helper_sha256"] == digest(Path(__file__).read_bytes()),
        "Report helper digest differs; regenerate this fixture's report",
    )
    saved_matches(report["task"], corpus["task"], "task")
    saved_matches(report["questions"], corpus["questions"], "questions")
    require(set(report["cases"]) == set(keys), "Expected all nine published cases")
    for key in keys:
        case, source = report["cases"][key], corpus["cases"][key]
        for field in ("seed", "length", "history_sha256", "expected"):
            saved_matches(case[field], source[field], f"{key}/{field}")
        lexical = len(LEXICAL.findall(source["history"]))
        require(
            case["history_characters"] == len(source["history"])
            and case["history_lexical_tokens"] == lexical,
            f"{key}: source counts differ",
        )
        require(set(case["runs"]) == set(CONDITIONS), f"{key}: four conditions required")
        for condition in CONDITIONS:
            row, label = case["runs"][condition], f"{key}/{condition}"
            budget = (
                None
                if condition == "full"
                else (
                    max(1024, math.ceil(lexical * 0.8))
                    if condition == "80"
                    else int(lexical * int(condition) / 100)
                )
            )
            require(
                row["status"] == "completed"
                and row["budget"] == budget
                and row["budget_omitted"] is (condition == "80"),
                f"{label}: status/budget differs",
            )
            require(
                row["selected_method"] == ("full_history" if condition == "full" else "tomc_raw"),
                f"{label}: recorded route differs",
            )
            items = set(row["item_types"])
            require(
                {"userMessage", "agentMessage"} <= items <= ALLOWED_ITEMS,
                f"{label}: answering items differ",
            )
            usage = checked_usage(row["provider_usage"], label)
            saved_matches(row["provider_usage"], usage, f"{label}/provider_usage")
            require(
                usage["inputTokens"] > 0 and bool(row["raw_usage_updates"]),
                f"{label}: usage absent",
            )
            for snapshot in row["raw_usage_updates"]:
                require(
                    set(snapshot) <= {"last", "total", "modelContextWindow"},
                    f"{label}: raw metadata differs",
                )
                for part in ("last", "total"):
                    require(
                        set(snapshot[part]) <= set(USAGE_FIELDS),
                        f"{label}: raw usage fields differ",
                    )
                    checked_usage(snapshot[part], label)
            final = row["raw_usage_updates"][-1]
            require(
                checked_usage(final["last"], label)
                == checked_usage(final["total"], label)
                == usage,
                f"{label}: final usage differs",
            )
            require(isinstance(row["answer"], str), f"{label}: answer missing")
            graded = grade_answer(row["answer"], source["expected"])
            saved_matches(row["regraded"], graded, f"{label}/regraded")
            saved_matches(
                row["regraded_value_matches"], graded["value_marks"], f"{label}/value_matches"
            )
            require(
                row["checked_value_score"] == graded["value_correct"], f"{label}: score differs"
            )
            for field in ("got", "claude_legacy_marks", "claude_legacy_correct"):
                saved_matches(row["original_grading"][field], graded[field], f"{label}/{field}")
            tokens = row["evidence_lexical_tokens"]
            for field in ("prompt_sha256", "evidence_sha256"):
                require(
                    re.fullmatch(r"[0-9a-f]{64}", row[field]) is not None,
                    f"{label}: invalid {field}",
                )
            if condition == "full":
                require(
                    row["evidence_sha256"] == source["history_sha256"],
                    f"{label}: reference evidence hash differs",
                )
            require(
                type(tokens) is int
                and (tokens == lexical if budget is None else 0 < tokens <= budget),
                f"{label}: evidence count differs",
            )
            saved_matches(
                row["actual_lexical_evidence_retention_pct"],
                100 * tokens / lexical,
                f"{label}/retention",
            )
            saved_matches(
                row["paired_provider_input_decrease_pct"],
                100
                * (
                    1 - usage["inputTokens"] / case["runs"]["full"]["provider_usage"]["inputTokens"]
                ),
                f"{label}/paired_input",
            )
            require(
                type(row["user_prompt_cl100k_tokens"]) is int
                and row["user_prompt_cl100k_tokens"] > 0,
                f"{label}: descriptive count absent",
            )
            require(
                row["provider_minus_cl100k_user_prompt_residual"]
                == usage["inputTokens"] - row["user_prompt_cl100k_tokens"],
                f"{label}: residual differs",
            )
            require(
                type(row["duration_seconds"]) in (int, float)
                and math.isfinite(row["duration_seconds"])
                and row["duration_seconds"] >= 0,
                f"{label}: invalid duration",
            )
    saved_matches(report["overall"], descriptive_summary(report["cases"], keys), "overall")
    per_length = {
        length: descriptive_summary(
            report["cases"], [key for key in keys if corpus["cases"][key]["length"] == length]
        )
        for length in LENGTHS
    }
    saved_matches(report["per_length"], per_length, "per_length")
    return {
        "status": "verified saved report",
        "cases": 9,
        "answering_turns": 36,
        "published_report_sha256": digest(path.read_bytes()),
        "scope": "Saved answers, usage accounting and aggregates verified offline; provider usage and model output were not regenerated.",
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--results", type=Path)
    parser.add_argument("--cases", type=Path)
    parser.add_argument("--output", type=Path, help="Sanitized JSON report file")
    parser.add_argument(
        "--verify-published", type=Path, help="Verify a saved report without host/model access"
    )
    args = parser.parse_args()
    if args.verify_published is not None:
        if any((args.results, args.cases, args.output)):
            parser.error("--verify-published cannot be combined with export arguments")
        print(json.dumps(verify_published(args.verify_published)))
        return
    if not all((args.results, args.cases, args.output)):
        parser.error("export mode requires --results, --cases and --output")
    require(
        args.output.resolve() not in {args.results.resolve(), args.cases.resolve()},
        "Output must not replace frozen source data",
    )
    report = audit_and_report(args.results, args.cases)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n"
    )
    print(json.dumps({"status": report["status"], "cases": 9, "answering_turns": 36}))


if __name__ == "__main__":
    main()
