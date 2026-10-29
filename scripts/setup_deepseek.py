"""Write an additive DSH MCP overlay using this Python environment's paths.

Run with the Python environment in which TOMC and its MCP extra are installed.
No DSH configuration, model credentials, or existing file is overwritten.
"""

from __future__ import annotations

import argparse
from pathlib import Path

from tomc.setup import client_config


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--store", type=Path)
    args = parser.parse_args()
    content = client_config("deepseek", args.store)
    target = args.output.expanduser().absolute()
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("x", encoding="utf-8", newline="\n") as stream:
        stream.write(content)
    print(f"Created DSH overlay: {target}")
    print("Launch DSH with --patch followed by this quoted path.")


if __name__ == "__main__":
    main()
