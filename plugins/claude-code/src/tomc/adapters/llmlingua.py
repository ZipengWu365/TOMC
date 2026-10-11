"""Thin optional adapter around the official library; no model loads on import."""

from __future__ import annotations

from typing import Any, Literal

from ..schemas import Source
from ..strategies.base import StrategyOutput
from ..tokenization import TokenCounter


class AdapterUnavailable(RuntimeError):
    """The official dependency/model has not been explicitly supplied."""


class LLMLinguaAdapter:
    """Wrap an explicitly initialized official PromptCompressor instance."""

    def __init__(
        self,
        compressor: Any = None,
        *,
        variant: Literal["llmlingua", "longllmlingua", "llmlingua2"] = "llmlingua2",
    ) -> None:
        """Model download and licensing decisions belong to the explicit caller setup."""
        if variant not in ("llmlingua", "longllmlingua", "llmlingua2"):
            raise ValueError("Unknown LLMLingua variant")
        self.compressor = compressor
        self.name = variant

    def compress(
        self, history: str, units: list[Source], query: str, budget: int, counter: TokenCounter
    ) -> StrategyOutput:
        """Call official compression; disclose any extra budget clipping by TOMC."""
        if self.compressor is None:
            raise AdapterUnavailable(
                "Install tomc-memory[llmlingua] and pass an explicitly initialized "
                "official PromptCompressor. No substitute result was produced."
            )
        if not history or budget == 0:
            return StrategyOutput("", self.name)
        kwargs: dict[str, Any] = {"target_token": budget}
        prompt: str | list[str] = history
        if self.name == "llmlingua":
            kwargs.update(instruction="", question=query)
        elif self.name == "longllmlingua":
            prompt = [u.text for u in units]
            kwargs.update(
                question=query,
                condition_in_question="after_condition",
                reorder_context="sort",
                dynamic_context_compression_ratio=0.3,
                condition_compare=True,
                context_budget="+100",
                rank_method="longllmlingua",
            )
        output = self.compressor.compress_prompt(prompt, **kwargs)
        text = output["compressed_prompt"]
        if not isinstance(text, str):
            raise ValueError("Official adapter returned non-text compressed_prompt")
        clipped = counter.count(text) > budget
        return StrategyOutput(
            counter.truncate(text, budget),
            self.name,
            warnings=["Official dependency output; no state ledger is inferred."]
            + (
                ["Additional clipping enforced the selected TOMC counter budget."]
                if clipped
                else []
            ),
            diagnostics={"official_adapter": True, "post_clipped": clipped},
        )
