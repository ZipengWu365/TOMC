"""Deterministic, inspectable routing rules; no learned accuracy claims."""

from __future__ import annotations

import re

from ._vendor import reference

# The paper's route predicates as whole words and phrases: "account", "discount" and
# "country" are not "count", "concurrent" is not "current", and "install path" is not
# a relation. An explicit "path:" or "relation:" label still selects relation paths.
_STATE = re.compile(
    r"\b(?:current|currently|final value|latest value|latest|ends? at)\b|\bnow\s*[?.!]?\s*$",
    re.I,
)
_COUNT = re.compile(
    r"\b(?:how many|how often|frequency|most frequent|common word|count|counts|counted|"
    r"number of times)\b",
    re.I,
)
_RELATION = re.compile(
    r"\b(?:related|relation|associated|credential|credentials|linked|which account)\b"
    r"|\bpath\s*[:=]",
    re.I,
)
_ZH_STATE = ("当前", "最终", "最新", "偏好", "约束", "现在", "目前", "如今", "最后", "改成")
_ZH_COUNT = ("多少次", "频率", "计数", "几次")
_ZH_RELATION = ("关系", "路径", "关联")


def task_route(query: str) -> reference.Route:
    """Use the paper route predicates as whole words, plus explicit Chinese task keywords."""
    if any(w in query for w in _ZH_STATE):
        return reference.Route.STATE
    if any(w in query for w in _ZH_COUNT):
        return reference.Route.COUNT
    if any(w in query for w in _ZH_RELATION):
        return reference.Route.RELATION
    if _STATE.search(query):
        return reference.Route.STATE
    if _COUNT.search(query):
        return reference.Route.COUNT
    if _RELATION.search(query):
        return reference.Route.RELATION
    return reference.Route.RAW


def hybrid_route(history: str, query: str) -> tuple[str, str]:
    """Choose paper operations for typed tasks and retain original source evidence."""
    if re.search(
        r"\b(why|explain|quote|verbatim|exact wording|summari[sz]e)\b", query, re.I
    ) or any(w in query for w in ("为什么", "原文", "解释", "总结")):
        return "tomc_raw", "Open semantics or exact wording needs source evidence."
    if task_route(query) != reference.Route.RAW:
        return "tomc_raw", "Typed task detected; retain raw evidence alongside compiled rows."
    return "rag", "No supported typed operation detected; use lexical source retrieval."
