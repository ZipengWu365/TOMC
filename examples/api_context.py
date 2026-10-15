"""Compare next-request text locally; build a payload without calling a model."""

from __future__ import annotations

import argparse
import json

from tomc import compile_memory, prepare_context
from tomc.tokenization import get_counter

HISTORY = """framework = Flask
backup_framework copies framework
framework = FastAPI
Monday notes: the team reviewed the project backlog, discussed deployment windows and agreed to keep the public API routes and response fields unchanged during the refactor.
Tuesday notes: the migration plan still needs a review from the database owner, and the pagination tests have not yet been written or run.
Wednesday notes: the team checked the release checklist, added a rollback task, and postponed the documentation update until after the test results are available."""
TASK = "What are the current framework and backup_framework values?"


def build_example(tokenizer: str = "regex") -> dict:
    """Compare identical instruction/task framing and return the prepared payload."""
    prepared = prepare_context(HISTORY, TASK, budget=64)
    original = compile_memory(HISTORY, TASK, 64, strategy="raw")
    counter = get_counter(tokenizer)

    def count_content(messages: list[dict[str, str]]) -> int:
        return sum(counter.count(message["content"]) for message in messages)

    before = count_content(original.reader_messages(TASK))
    after = count_content(prepared.messages)
    return {
        "counter": counter.name,
        "scope": "Message text including the same instructions and task; excludes provider chat framing, tool schemas and hidden tokens. Not billed usage.",
        "memory_budget": "64 lexical-estimate tokens; the message-text counter below can be different",
        "message_text_before": before,
        "message_text_after": after,
        "message_text_saved_percent": round((1 - after / before) * 100, 2),
        "selected_method": prepared.compilation.diagnostics["selected_strategy"],
        "payload": {"messages": prepared.messages},
        "next_step": "Use this messages payload instead of the original history in your next model request. Preserve any additional application instructions. No API call was made by this example.",
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tokenizer", default="regex")
    args = parser.parse_args()
    print(json.dumps(build_example(args.tokenizer), ensure_ascii=False, indent=2))
