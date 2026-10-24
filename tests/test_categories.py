"""Kinds of work describe a conversation in a feedback report without naming it."""

import re
from types import SimpleNamespace

import pytest

from tomc.categories import CATEGORIES, CODES, classify, label


@pytest.mark.parametrize(
    ("text", "code"),
    [
        ("修复小猫不进阶", "coding"),
        ("Fix the failing gateway test", "coding"),
        ("润色论文引言", "paper"),
        ("Rebuttal for the NeurIPS reviewers", "paper"),
        ("Draft a blog post about memory", "writing"),
        ("剪辑视频并加字幕", "video"),
        ("Design the app icon in Figma", "design"),
        ("Clean the sales CSV with pandas", "data"),
        ("小红书宣传文案", "marketing"),
        ("学习 Rust 的教程笔记", "learning"),
    ],
)
def test_common_kinds_of_work(text, code):
    assert classify(text) == code


def test_ascii_keywords_match_whole_words_only():
    # "ci" must not match "social", nor "tex" match "context".
    assert classify("social") == "marketing"
    assert classify("context") == "other"
    assert classify("CI is red") == "coding"


def test_the_conversation_name_counts_double_and_ties_keep_table_order():
    assert classify("论文", "debug") == "paper"
    assert classify("debug", "论文") == "coding"
    assert classify(None, "论文 debug") == "coding"  # a tie: coding comes first


def test_nothing_recognisable_is_other():
    assert classify() == classify(None, "", "   ") == classify("今天天气不错") == "other"


def test_every_kind_has_both_labels():
    assert CODES[-1] == "other" and len(set(CODES)) == len(CODES)
    for code in CODES:
        assert label(code, "zh") and not re.search(r"[A-Za-z]{3}", label(code, "zh"))
        assert label(code, "en") and not re.search(r"[㐀-鿿]", label(code, "en"))
    assert label("coding") == "编程开发"
    assert label("coding", SimpleNamespace(code="en")) == "Coding"
    assert label("unknown", "en") == "Other"
    assert all(keywords for code, _zh, _en, keywords in CATEGORIES if code != "other")
