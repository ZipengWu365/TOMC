"""Prepare every request from original history; offline by default, --live sends requests."""

from __future__ import annotations

import argparse
import json
import time

from tomc import compile_memory, prepare_context
from tomc.adapters.reader import APIReader
from tomc.input import parse_history
from tomc.tokenization import get_counter


def run_turn(
    history: list[dict[str, str]],
    task: str,
    *,
    budget: int = 64,
    instructions: str = "Answer briefly and preserve exact identifiers.",
    reader: APIReader | None = None,
) -> dict:
    """Replace request history, keeping original evidence for the next task.

    This text-only example is not an SDK interceptor or a tool-call continuation
    adapter. Keep live tool-call envelopes outside this evidence-preparation path.
    No result cache or incremental compiler is used. A dry run leaves history
    unchanged; a successful live turn appends the actual task and answer only.
    """
    started = time.perf_counter()
    prepared = prepare_context(history, task, budget)
    preparation_ms = (time.perf_counter() - started) * 1000
    if not prepared.prompt:
        raise ValueError(prepared.note)
    messages = [dict(message) for message in prepared.messages]
    messages[0]["content"] = instructions + "\n\n" + messages[0]["content"]

    # Use identical task/instruction framing for the uncompressed comparison.
    original = compile_memory(parse_history(history), task.strip(), budget, "raw")
    original_messages = original.reader_messages(task.strip())
    original_messages[0]["content"] = instructions + "\n\n" + original_messages[0]["content"]
    counter = get_counter("regex")
    report = {
        "task": task,
        "mode": "live" if reader is not None else "dry-run",
        "preparation_ms": round(preparation_ms, 3),
        "selected_strategy": prepared.compilation.diagnostics["selected_strategy"],
        "original_message_text_tokens": sum(counter.count(m["content"]) for m in original_messages),
        "prepared_message_text_tokens": sum(counter.count(m["content"]) for m in messages),
        "count_scope": "Lexical estimates of message text; excludes tool schemas and provider framing. Not billed usage.",
        "provider_usage": None,
    }
    if reader is None:
        report["messages"] = messages
        return report

    started = time.perf_counter()
    response = reader.complete(messages)
    report["reader_ms"] = round((time.perf_counter() - started) * 1000, 3)
    report["provider_usage"] = response.usage
    report["answer"] = response.text
    report["finish_reason"] = response.finish_reason
    history.extend(
        [{"role": "user", "content": task}, {"role": "assistant", "content": response.text}]
    )
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--live", action="store_true", help="Send two potentially billable model requests."
    )
    args = parser.parse_args()
    reader = APIReader() if args.live else None
    history = [
        {
            "role": "user",
            "content": "\n".join(
                [
                    "framework = Flask",
                    "backup_framework copies framework",
                    "framework = FastAPI",
                    "The database migration failed because the invoices table was locked.",
                    *[
                        f"Planning note {i}: reviewed the backlog and postponed unrelated deployment discussion."
                        for i in range(12)
                    ],
                ]
            ),
        }
    ]
    for task in (
        "What are the current framework and backup_framework values?",
        "Why did the database migration fail?",
    ):
        print(json.dumps(run_turn(history, task, reader=reader), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
