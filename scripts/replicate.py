"""Opt-in API replication harness for user-owned data. Dry-run is the default."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
from datetime import datetime, timezone
from pathlib import Path

from tomc import STRATEGIES, __version__, compile_memory
from tomc.adapters.reader import APIReader
from tomc.tokenization import RegexCounter


def digest(value: object) -> str:
    """Hash canonical UTF-8 JSON, without persisting its potentially private text."""
    return hashlib.sha256(
        json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def main() -> None:
    """Plan requests and estimated upper output cost before an explicitly opted-in run."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("data", type=Path, help="JSONL: {messages, query, reference_answer?}")
    parser.add_argument("--strategies", nargs="+", choices=STRATEGIES, default=["raw", "tomc_raw"])
    parser.add_argument("--budget", type=int, default=4096)
    parser.add_argument("--max-output-tokens", type=int, default=256)
    parser.add_argument(
        "--input-price", type=float, required=True, help="Your currency / 1M input tokens"
    )
    parser.add_argument("--output-price", type=float, required=True)
    parser.add_argument(
        "--max-cost", type=float, default=0, help="Estimated cost ceiling required for --execute"
    )
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--retries", type=int, default=0)
    parser.add_argument(
        "--dry-run", action="store_true", help="Explicit planning-only mode (also the default)"
    )
    parser.add_argument(
        "--execute", action="store_true", help="Explicitly permit paid reader requests"
    )
    parser.add_argument(
        "--save-answers",
        action="store_true",
        help="Save answers locally in an ignored private file",
    )
    parser.add_argument("--output", type=Path, default=Path("outputs/replication"))
    args = parser.parse_args()
    if any(
        not math.isfinite(x) or x < 0 for x in (args.input_price, args.output_price, args.max_cost)
    ):
        parser.error("Prices and cost ceiling must be finite and nonnegative")
    if args.max_output_tokens <= 0 or not 0 <= args.retries <= 5:
        parser.error("Positive output limit and retries in [0,5] are required")
    if args.execute and args.dry_run:
        parser.error("Choose --execute or --dry-run")
    data = [json.loads(line) for line in args.data.read_text().splitlines() if line.strip()]
    counter = RegexCounter()
    jobs, public_jobs = [], []
    for i, row in enumerate(data):
        for strategy in args.strategies:
            result = compile_memory(row["messages"], row["query"], args.budget, strategy)
            messages = result.reader_messages(row["query"])
            tokens = counter.count(json.dumps(messages, ensure_ascii=False))
            job = {
                "ordinal": i,
                "strategy": strategy,
                "prompt_hash": digest(messages),
                "estimated_input_tokens": tokens,
            }
            public_jobs.append(job)
            jobs.append((job, messages, row.get("reference_answer")))
    estimated = (
        (
            sum(j["estimated_input_tokens"] for j in public_jobs) * args.input_price
            + len(jobs) * args.max_output_tokens * args.output_price
        )
        / 1e6
        * (args.retries + 1)
    )
    manifest = {
        "schema": "tomc-replication-v1",
        "tomc_version": __version__,
        "time_utc": datetime.now(timezone.utc).isoformat(),
        "data_sha256": hashlib.sha256(args.data.read_bytes()).hexdigest(),
        "model": os.environ.get("TOMC_READER_MODEL", "not_configured"),
        "seed": args.seed,
        "temperature": 0.0,
        "budget": args.budget,
        "max_output_tokens": args.max_output_tokens,
        "requests": len(jobs),
        "maximum_attempts": len(jobs) * (args.retries + 1),
        "estimated_cost_with_retries": estimated,
        "input_price_per_million": args.input_price,
        "output_price_per_million": args.output_price,
        "cost_note": "Lexical estimate, not a hard billing cap. Hidden provider tokens and model updates may differ.",
        "dry_run": not args.execute,
        "jobs": public_jobs,
    }
    args.output.mkdir(parents=True, exist_ok=True)
    (args.output / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    print(json.dumps({k: v for k, v in manifest.items() if k != "jobs"}, indent=2))
    if not args.execute:
        return
    if args.max_cost <= 0 or estimated > args.max_cost:
        parser.error("Estimated cost exceeds --max-cost or the execute cost ceiling is missing")
    reader = APIReader(retries=args.retries)
    with (args.output / "results.jsonl").open("x") as out:
        for job, messages, reference in jobs:
            answer = reader.complete(messages, max_tokens=args.max_output_tokens, seed=args.seed)
            result = {
                **job,
                "response_model": answer.model,
                "usage": answer.usage,
                "finish_reason": answer.finish_reason,
                "answer_hash": digest(answer.text),
                "exact_match": answer.text.strip() == reference.strip()
                if isinstance(reference, str)
                else None,
            }
            out.write(json.dumps(result) + "\n")
            out.flush()
            if args.save_answers:
                with (args.output / "answers.private.jsonl").open("a") as private:
                    private.write(json.dumps({**job, "answer": answer.text}) + "\n")


if __name__ == "__main__":
    main()
