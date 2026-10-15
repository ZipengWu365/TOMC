"""Remove optional stock CDN startup resources from the local/Space HTML shell."""

import re

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response


def offline_shell(body: bytes) -> bytes:
    """Strip Gradio's optional iframe-resizer CDN script and Google font preconnects."""
    body = re.sub(
        rb'<script\b[^>]*src="https://cdnjs\.cloudflare\.com/ajax/libs/iframe-resizer/[^">]+"[^>]*>\s*</script>',
        b"",
        body,
    )
    return re.sub(
        rb'<link\b[^>]*href="https://fonts\.(?:googleapis|gstatic)\.com"[^>]*>', b"", body
    )


class OfflineHTMLMiddleware(BaseHTTPMiddleware):
    """Only adapt the initial HTML document; API calls and static assets are untouched."""

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        """Serve a self-contained shell using Gradio's locally installed JavaScript/fonts."""
        response = await call_next(request)
        if request.url.path != "/" or "text/html" not in response.headers.get("content-type", ""):
            return response
        chunks = [chunk async for chunk in response.body_iterator]
        body = b"".join(chunk.encode() if isinstance(chunk, str) else chunk for chunk in chunks)
        headers = dict(response.headers)
        headers.pop("content-length", None)
        return Response(
            offline_shell(body),
            status_code=response.status_code,
            headers=headers,
            background=response.background,
        )
