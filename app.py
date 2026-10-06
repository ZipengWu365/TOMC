"""Space entry point; bootstrap bundled source after the Hub copies the checkout."""

import sys
from pathlib import Path


def main() -> None:
    """Launch bundled code; Spaces installs requirements before copying project files."""
    sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))
    from starlette.middleware import Middleware

    from demo.app import create_demo
    from demo.offline import OfflineHTMLMiddleware

    create_demo().queue(default_concurrency_limit=2, max_size=24).launch(
        server_name="0.0.0.0",
        server_port=7860,
        share=False,
        # The optional Node SSR proxy bypasses the offline HTML middleware.
        ssr_mode=False,
        show_error=False,
        enable_monitoring=False,
        app_kwargs={"middleware": [Middleware(OfflineHTMLMiddleware)]},
    )


if __name__ == "__main__":
    main()
