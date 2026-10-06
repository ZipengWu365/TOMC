"""Download a user-selected licensed data artifact only with its expected SHA-256."""

import argparse
import hashlib
import os
import tempfile
from pathlib import Path
from urllib.parse import urlsplit
from urllib.request import urlopen


def main() -> None:
    """Verify before atomically installing a file; never extract arbitrary archives."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("url")
    parser.add_argument("--sha256", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if urlsplit(args.url).scheme != "https" or len(args.sha256) != 64:
        parser.error("HTTPS URL and a 64-character expected SHA-256 are required")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    if args.output.exists():
        parser.error("Output already exists")
    digest = hashlib.sha256()
    fd, temporary = tempfile.mkstemp(dir=args.output.parent)
    try:
        with os.fdopen(fd, "wb") as out, urlopen(args.url, timeout=60) as response:
            while chunk := response.read(1024 * 1024):
                digest.update(chunk)
                out.write(chunk)
        if digest.hexdigest() != args.sha256.lower():
            raise ValueError("Downloaded data SHA-256 mismatch")
        Path(temporary).replace(args.output)
    finally:
        Path(temporary).unlink(missing_ok=True)
    print("Verified download complete.")


if __name__ == "__main__":
    main()
