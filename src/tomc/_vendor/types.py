from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class CompressionOutput:
    """Normalized output shared by frozen legacy methods and TOMC2 methods."""

    text: str
    method: str
    budget_tokens: int
    approx_tokens: int
    selected_indices: list[int] = field(default_factory=list)
    diagnostics: dict[str, Any] = field(default_factory=dict)
    implementation_sha256: str = ""
