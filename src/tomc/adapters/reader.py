"""Environment-only reader credentials and bounded, sanitized HTTP handling."""

from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener


class ReaderError(RuntimeError):
    """A sanitized failure; category supports retry-aware downstream handling."""

    def __init__(self, category: str, status: int | None = None) -> None:
        """Store error category without response body, request, endpoint, or key."""
        self.category = category
        self.status = status
        super().__init__(
            f"Reader request failed: {category}" + (f" (HTTP {status})" if status else "")
        )


class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


@dataclass(frozen=True)
class ReaderResponse:
    """Delivered answer and provider-reported usage, without headers or raw payload."""

    text: str
    model: str
    usage: dict[str, int]
    finish_reason: str


class APIReader:
    """Opt-in chat-completions-compatible reader. Creating it makes no requests."""

    def __init__(self, *, timeout: float = 30, retries: int = 2) -> None:
        """Read TOMC_READER_API_KEY, TOMC_READER_BASE_URL, and TOMC_READER_MODEL."""
        if timeout <= 0 or not 0 <= retries <= 5:
            raise ValueError("Use a positive timeout and between zero and five retries")
        self._key = os.environ.get("TOMC_READER_API_KEY", "")
        base = os.environ.get("TOMC_READER_BASE_URL", "").rstrip("/")
        self.model = os.environ.get("TOMC_READER_MODEL", "")
        parsed = urlsplit(base)
        if not self._key or not base or not self.model:
            raise ReaderError("configuration_missing")
        if (
            parsed.username
            or parsed.password
            or parsed.query
            or parsed.fragment
            or not parsed.hostname
            or parsed.scheme not in ("https", "http")
        ):
            raise ReaderError("invalid_endpoint")
        if parsed.scheme == "http" and parsed.hostname not in ("localhost", "127.0.0.1", "::1"):
            raise ReaderError("https_required")
        self._url = base + "/chat/completions"
        self.timeout, self.retries = timeout, retries
        self._opener = build_opener(_NoRedirect())

    def complete(
        self,
        messages: list[dict[str, str]],
        *,
        max_tokens: int = 256,
        temperature: float = 0.0,
        seed: int | None = None,
    ) -> ReaderResponse:
        """Explicitly send memory to the configured reader; never log request/response bodies."""
        if isinstance(max_tokens, bool) or not isinstance(max_tokens, int) or max_tokens <= 0:
            raise ValueError("max_tokens must be a positive integer")
        payload: dict[str, object] = {
            "model": self.model,
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": temperature,
        }
        if seed is not None:
            payload["seed"] = seed
        request = Request(
            self._url,
            data=json.dumps(payload).encode(),
            method="POST",
            headers={"Content-Type": "application/json", "Authorization": "Bearer " + self._key},
        )
        failure = ReaderError("transport")
        for attempt in range(self.retries + 1):
            try:
                with self._opener.open(request, timeout=self.timeout) as response:
                    body = response.read(2_000_001)
                if len(body) > 2_000_000:
                    raise ReaderError("response_too_large")
                data = json.loads(body)
                choice = data["choices"][0]
                answer = choice["message"]["content"]
                if not isinstance(answer, str):
                    raise ReaderError("invalid_response")
                usage = {
                    k: int(v)
                    for k, v in data.get("usage", {}).items()
                    if k in ("prompt_tokens", "completion_tokens", "total_tokens")
                    and isinstance(v, int)
                }
                return ReaderResponse(
                    answer,
                    str(data.get("model", self.model)),
                    usage,
                    str(choice.get("finish_reason", "unknown")),
                )
            except HTTPError as exc:
                code = exc.code
                exc.close()
                category = (
                    "authentication"
                    if code in (401, 403)
                    else "rate_limit"
                    if code == 429
                    else "server"
                    if code >= 500
                    else "request"
                )
                failure = ReaderError(category, code)
                if code != 429 and code < 500:
                    raise failure from None
            except (URLError, TimeoutError, OSError):
                failure = ReaderError("transport_or_timeout")
            except (ValueError, KeyError, IndexError, TypeError):
                raise ReaderError("invalid_response") from None
            if attempt < self.retries:
                time.sleep(min(2**attempt, 4))
        raise failure from None
