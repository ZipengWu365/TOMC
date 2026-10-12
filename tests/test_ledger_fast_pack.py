"""Output-equivalence checks for the builtin lexical newline-packing fast path."""

from __future__ import annotations

import random

import pytest

from tomc import ledger as candidate
from tomc.ledger import pack_rows as original_pack_rows
from tomc.tokenization import RegexCounter


class WrappedSlowCounter:
    """Same lexical counts through the unchanged generic full-candidate branch."""

    name = "regex-v1 (estimate)"
    estimated = True

    def __init__(self):
        self.wrapped = RegexCounter()

    def count(self, text):
        return self.wrapped.count(text)


@pytest.mark.parametrize("seed", range(30))
def test_random_rows_match_wrapped_slow_counter_text_keys_order_and_budget(seed):
    rng = random.Random(seed)
    fragments = [
        "",
        " ",
        "\t",
        "\r\n",
        "\n",
        "word",
        "word_",
        "_word",
        "a_b",
        "__",
        "中文",
        "🙂",
        "!?",
        "[RAW u1]",
        "e\u0301",
        "\0",
    ]
    rows = [
        (f"key_{index % 7}", "".join(rng.choice(fragments) for _ in range(rng.randrange(0, 18))))
        for index in range(rng.randrange(0, 45))
    ]
    total = RegexCounter().count("\n".join(row for _, row in rows))
    assert total == sum(RegexCounter().count(row) for _, row in rows)
    budgets = {0, 1, 2, 7, 19, total, total + 1, *[rng.randrange(0, total + 2) for _ in range(8)]}
    for budget in budgets:
        fast = candidate.pack_rows(rows, budget, RegexCounter())
        slow = candidate.pack_rows(rows, budget, WrappedSlowCounter())
        archived = original_pack_rows(rows, budget, RegexCounter())
        assert fast == slow == archived
        assert RegexCounter().count(fast[0]) <= budget


class CharacterCounter:
    # A misleading name must never establish additive newline semantics.
    name = "regex-v1 (estimate)"
    estimated = True

    def count(self, text):
        return len(text)


class CharacterSubclass(RegexCounter):
    def count(self, text):
        return len(text)


class MutableCounter:
    name = "mutable custom counter"
    estimated = True

    def __init__(self):
        self.calls = 0

    def count(self, text):
        self.calls += 1
        return len(text) + self.calls % 2


@pytest.mark.parametrize("counter_type", [CharacterCounter, CharacterSubclass, MutableCounter])
def test_other_counter_types_keep_original_full_candidate_behavior(counter_type):
    rows = [("a", "abc"), ("b", "def"), ("a", ""), ("d", "hi"), ("e", "中文")]
    for budget in range(15):
        first, second = counter_type(), counter_type()
        assert candidate.pack_rows(rows, budget, first) == original_pack_rows(rows, budget, second)
        if counter_type is MutableCounter:
            assert first.calls == second.calls


def test_instance_overridden_builtin_count_uses_original_generic_behavior():
    rows = [("a", "abc"), ("b", "def"), ("c", "hi")]
    for budget in range(12):
        overridden = RegexCounter()
        overridden.count = lambda text: len(text)
        assert candidate.pack_rows(rows, budget, overridden) == original_pack_rows(
            rows, budget, CharacterCounter()
        )
