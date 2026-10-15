"""Dated official model limits for request planning, with no network discovery."""

from __future__ import annotations

import json
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path


@dataclass(frozen=True)
class ModelProfile:
    provider: str
    model_id: str
    context_tokens: int
    default_context_tokens: int
    max_input_tokens: int | None
    max_output_tokens: int | None
    window_semantics: str
    precision: str
    checked_on: str
    sources: tuple[str, ...]

    def input_budget(
        self,
        *,
        output_reserve: int,
        deployment_context_limit: int | None = None,
        extra_prompt_tokens: int = 0,
    ) -> int:
        """Reserve output and non-message prompt fields using published semantics.

        Deployment/agent limits can only narrow a documented maximum. Gemini's
        documented input limit is handled separately from its output limit.
        Unspecified combined-window semantics are treated conservatively.
        Counts supplied by the caller may be estimates, not provider accounting.
        """
        for name, value in (
            ("output_reserve", output_reserve),
            ("extra_prompt_tokens", extra_prompt_tokens),
        ):
            if isinstance(value, bool) or not isinstance(value, int) or value < 0:
                raise ValueError(f"{name} must be a nonnegative integer")
        context = self.default_context_tokens
        if deployment_context_limit is not None:
            if (
                isinstance(deployment_context_limit, bool)
                or not isinstance(deployment_context_limit, int)
                or deployment_context_limit < 1
            ):
                raise ValueError("deployment_context_limit must be a positive integer")
            context = min(self.context_tokens, deployment_context_limit)
        available = context if self.window_semantics == "input_only" else context - output_reserve
        if self.max_input_tokens is not None:
            available = min(available, self.max_input_tokens)
        return max(0, available - extra_prompt_tokens)


@lru_cache(maxsize=1)
def _profiles() -> tuple[ModelProfile, ...]:
    data = json.loads(
        (Path(__file__).parent / "data/model_contexts_20261012.json").read_text(encoding="utf-8")
    )
    return tuple(
        ModelProfile(
            row["provider"],
            row["model_id"],
            row["context_tokens"],
            row.get("default_context_tokens") or row["context_tokens"],
            row.get("max_input_tokens"),
            row.get("max_output_tokens"),
            row["window_semantics"],
            row["precision"],
            data["checked_on"],
            tuple(row["sources"]),
        )
        for row in data["models"]
    )


def get_model_profile(model_id: str, provider: str | None = None) -> ModelProfile | None:
    """Match an exact documented ID; never guess all models have a 1M/10M window."""
    matches = [
        profile
        for profile in _profiles()
        if profile.model_id == model_id and (provider is None or profile.provider == provider)
    ]
    return matches[0] if len(matches) == 1 else None
