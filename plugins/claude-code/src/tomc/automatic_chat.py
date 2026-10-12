"""Opt-in preprocessing for a caller-controlled synchronous Chat Completions loop."""

from __future__ import annotations

import json
import threading
import uuid
from collections.abc import Mapping, Sequence
from typing import Any

from .model_profiles import get_model_profile
from .native_events import extract_state
from .request_context import NativeState, RequestContextManager, RequestContextPlan
from .tokenization import RegexCounter


def _task_from_messages(messages: Sequence[Mapping[str, Any]]) -> str:
    for message in reversed(messages):
        if message.get("role") != "user":
            continue
        content = message.get("content")
        if isinstance(content, str):
            return content.strip()
        if isinstance(content, list):
            return "\n".join(
                part["text"]
                for part in content
                if isinstance(part, dict)
                and part.get("type") in {"text", "input_text"}
                and isinstance(part.get("text"), str)
            ).strip()
    return ""


class AutomaticChatSession:
    """One chat's request views; original messages and provider responses stay with the caller.

    Model limits are looked up locally only at model changes. Native events must
    come from the caller's trusted host connection, not model-generated tool output.
    Only actual compaction events suspend optimization; supported/enabled flags do
    not disable it. Completed compaction skips one or two logical API requests,
    after which an eligible native summary may be optimized again.
    This is not a proxy, SDK monkeypatch or installed native-client event listener.
    """

    def __init__(
        self,
        *,
        memory_budget: int | None = None,
        refresh_every: int = 2,
        recent_messages: int = 6,
        request_budget: int | None = None,
        native_cooldown_requests: int = 2,
        native_state: NativeState = "unknown",
        provider: str | None = None,
        deployment_context_limit: int | None = None,
        output_reserve: int = 8192,
    ) -> None:
        if native_state not in {"idle", "active", "completed", "unknown"}:
            raise ValueError("Use idle, active, completed or unknown for native_state.")
        self.manager = RequestContextManager(
            memory_budget=memory_budget,
            refresh_every=refresh_every,
            recent_messages=recent_messages,
            request_budget=request_budget,
            native_cooldown_requests=native_cooldown_requests,
        )
        self._session_key = uuid.uuid4().hex
        self._native_state = native_state
        self._lock = threading.Lock()
        self.last_plan: RequestContextPlan | None = None
        self._provider = provider
        self._deployment_context_limit = deployment_context_limit
        if (
            isinstance(output_reserve, bool)
            or not isinstance(output_reserve, int)
            or output_reserve < 0
        ):
            raise ValueError("output_reserve must be a nonnegative integer")
        self._output_reserve = output_reserve
        self._explicit_request_budget = request_budget
        self._profile_model: str | None = None
        self._profile = None
        self._counter = RegexCounter()
        self._seen_boundaries: set[float] = set()
        self._last_provider_input_tokens: int | None = None

    def on_native_event(self, host: str, event: object) -> bool:
        """Accept only recognized real compaction lifecycle notifications."""
        state = extract_state(host, event)
        if state is None:
            return False
        with self._lock:
            self._native_state = state
            if state == "completed":
                self._seen_boundaries.clear()
                self._last_provider_input_tokens = None
        return True

    def set_native_state(self, state: NativeState) -> None:
        """Set caller-known state; supported/enabled capability is not an event."""
        if state not in {"idle", "active", "completed", "unknown"}:
            raise ValueError("Use idle, active, completed or unknown for native_state.")
        with self._lock:
            self._native_state = state

    def create(
        self,
        client: Any,
        *,
        messages: Sequence[Mapping[str, Any]],
        task: str | None = None,
        native_state: NativeState | None = None,
        context_tokens: int | None = None,
        **options: Any,
    ) -> Any:
        """Prepare each logical request, then call the unchanged client/provider.

        Model, tools, tool_choice, output limits and stream options are forwarded
        unchanged. The existing SDK handles transport retries of this prepared
        payload; the wrapper makes no extra model requests. Use a separate session
        object per conversation. Only synchronous Chat Completions is supported.
        """
        query = _task_from_messages(messages) if task is None else task
        with self._lock:
            state = self._native_state if native_state is None else native_state
            model = options.get("model")
            if model != self._profile_model:
                self._profile = (
                    get_model_profile(model, self._provider) if isinstance(model, str) else None
                )
                self._profile_model = model
                self._seen_boundaries.clear()
                self._last_provider_input_tokens = None
            reserve = options.get("max_completion_tokens")
            if reserve is None:
                reserve = options.get("max_tokens")
            if reserve is None:
                reserve = self._output_reserve
            if isinstance(reserve, bool) or not isinstance(reserve, int) or reserve < 0:
                raise ValueError("Use a nonnegative integer output reserve or output limit.")
            framing = {
                name: options[name]
                for name in ("tools", "response_format")
                if options.get(name) is not None
            }
            passthrough_reason = None
            try:
                extra = (
                    self._counter.count(json.dumps(framing, ensure_ascii=False)) if framing else 0
                )
            except (TypeError, ValueError):
                extra = 0
                passthrough_reason = "unsupported_prompt_options"
            limit = None
            effective_window = self._deployment_context_limit
            if self._profile is not None:
                effective_window = self._profile.default_context_tokens
                if self._deployment_context_limit is not None:
                    effective_window = min(
                        self._profile.context_tokens, self._deployment_context_limit
                    )
                limit = self._profile.input_budget(
                    output_reserve=reserve,
                    deployment_context_limit=self._deployment_context_limit,
                    extra_prompt_tokens=extra,
                )
            elif self._deployment_context_limit is not None:
                limit = max(0, self._deployment_context_limit - reserve - extra)
            if self._explicit_request_budget is not None:
                limit = (
                    self._explicit_request_budget
                    if limit is None
                    else min(limit, self._explicit_request_budget)
                )
            if limit is None or limit < 1:
                passthrough_reason = "model_budget_unavailable"
                limit = None
            if context_tokens is not None:
                if (
                    isinstance(context_tokens, bool)
                    or not isinstance(context_tokens, int)
                    or context_tokens < 0
                ):
                    raise ValueError("context_tokens must be a nonnegative integer")
                boundary_hint = context_tokens
            elif self._last_provider_input_tokens is not None:
                boundary_hint = self._last_provider_input_tokens
            else:
                # O(message count), not a scan of every character: coarse hint only.
                chars = 0
                for message in messages:
                    content = message.get("content")
                    if isinstance(content, str):
                        chars += len(content)
                    for call in message.get("tool_calls") or []:
                        if isinstance(call, Mapping):
                            function = call.get("function")
                            if isinstance(function, Mapping) and isinstance(
                                function.get("arguments"), str
                            ):
                                chars += len(function["arguments"])
                boundary_hint = (chars + 3) // 4
            if effective_window is not None and passthrough_reason is None:
                if boundary_hint < effective_window * 0.4:
                    self._seen_boundaries.clear()
                crossed = {
                    fraction
                    for fraction in (0.5, 0.9)
                    if boundary_hint >= effective_window * fraction
                    and fraction not in self._seen_boundaries
                }
                if crossed:
                    self._seen_boundaries.update(crossed)
                    passthrough_reason = "model_window_boundary_backoff"
            plan = self.manager.prepare(
                messages,
                query,
                native_state=state,
                session_key=self._session_key,
                request_budget=limit,
                passthrough_reason=passthrough_reason,
            )
            self.last_plan = plan
            if state == "completed":
                # Consume this event once; the manager counts its cooldown.
                self._native_state = "idle"
            elif native_state is not None:
                self._native_state = native_state
        response = client.chat.completions.create(messages=plan.messages, **options)
        # Never consume a stream. Usage metadata, when already present, is a hint
        # for the next request; it is not a native-compaction event.
        usage = (
            response.get("usage")
            if isinstance(response, Mapping)
            else getattr(response, "usage", None)
        )
        value = (
            usage.get("prompt_tokens")
            if isinstance(usage, Mapping)
            else getattr(usage, "prompt_tokens", None)
        )
        if isinstance(value, int) and not isinstance(value, bool) and value >= 0:
            with self._lock:
                self._last_provider_input_tokens = value
        return response
