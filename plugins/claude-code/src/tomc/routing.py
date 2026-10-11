"""Deterministic, inspectable routing rules; no learned accuracy claims."""

from __future__ import annotations

import re

from ._vendor import reference


def task_route(query: str) -> reference.Route:
    """Use the paper route predicates plus explicit Chinese task keywords."""
    if any(w in query for w in ("当前", "最终值", "最新", "偏好", "约束")):
        return reference.Route.STATE
    if any(w in query for w in ("多少次", "频率", "计数")):
        return reference.Route.COUNT
    if any(w in query for w in ("关系", "路径", "关联")):
        return reference.Route.RELATION
    return reference.default_route(query)


def hybrid_route(history: str, query: str) -> tuple[str, str]:
    """Choose paper operations for typed tasks and retain original source evidence."""
    if re.search(
        r"\b(why|explain|quote|verbatim|exact wording|summari[sz]e)\b", query, re.I
    ) or any(w in query for w in ("为什么", "原文", "解释", "总结")):
        return "tomc_raw", "Open semantics or exact wording needs source evidence."
    if task_route(query) != reference.Route.RAW:
        return "tomc_raw", "Typed task detected; retain raw evidence alongside compiled rows."
    return "rag", "No supported typed operation detected; use lexical source retrieval."
