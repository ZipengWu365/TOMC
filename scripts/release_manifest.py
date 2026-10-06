"""Create or verify per-file hashes for the exact reviewable release content."""

from __future__ import annotations

import argparse
import hashlib
import json

from security_scan import ROOT, candidates

SELF = {"PUBLIC_RELEASE_MANIFEST.json", "SHA256SUMS"}


def manifest() -> dict:
    """Build a stable manifest; exclude its own files to avoid recursive hashes."""
    entries = []
    # pathlib uses different case ordering on Windows and POSIX.
    for path in sorted(candidates(), key=lambda p: p.relative_to(ROOT).as_posix()):
        relative = path.relative_to(ROOT).as_posix()
        if relative in SELF:
            continue
        if path.is_symlink() or not path.is_file():
            raise ValueError("Release files must be regular files")
        data = path.read_bytes()
        entries.append(
            {"path": relative, "bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()}
        )
    return {
        "schema": "tomc-public-release-v1",
        "visibility": "private-staging",
        "public_release_authorized": False,
        "version": "0.1.0",
        "files": entries,
        "total_bytes": sum(x["bytes"] for x in entries),
        "self_excluded": sorted(SELF),
        "note": "Public-safe content inventory; public publication still requires owner approval. "
        "Commit identity is external because embedding its own final SHA would be recursive.",
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    result = manifest()
    path = ROOT / "PUBLIC_RELEASE_MANIFEST.json"
    sums = "".join(f"{x['sha256']}  {x['path']}\n" for x in result["files"])
    if args.check:
        if json.loads(path.read_text()) != result or (ROOT / "SHA256SUMS").read_text() != sums:
            raise SystemExit("Release manifest drift")
        print(f"Verified {len(result['files'])} release file hashes.")
    else:
        path.write_text(json.dumps(result, indent=2) + "\n")
        (ROOT / "SHA256SUMS").write_text(sums)
        print(f"Manifest created for {len(result['files'])} files, {result['total_bytes']} bytes.")
