"""Upload only verified release files to a private CPU Gradio Space."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path, PurePosixPath
from tempfile import TemporaryDirectory

from huggingface_hub import HfApi
from huggingface_hub.errors import RepositoryNotFoundError

ROOT = Path(__file__).resolve().parents[1]
SELF = {"PUBLIC_RELEASE_MANIFEST.json", "SHA256SUMS"}


def verify_staging(staging: Path) -> dict:
    """Check the exact staged inventory and hashes, including the Space README."""
    manifest = json.loads((staging / "PUBLIC_RELEASE_MANIFEST.json").read_text())
    paths = {entry["path"] for entry in manifest["files"]}
    actual = {path.relative_to(staging).as_posix() for path in staging.rglob("*") if path.is_file()}
    if actual != paths | SELF:
        raise ValueError("HF staging inventory does not match its manifest")
    total_bytes = 0
    for entry in manifest["files"]:
        path = staging / entry["path"]
        data = path.read_bytes()
        if (
            path.is_symlink()
            or len(data) != entry["bytes"]
            or hashlib.sha256(data).hexdigest() != entry["sha256"]
        ):
            raise ValueError(f"HF staging hash mismatch: {entry['path']}")
        total_bytes += len(data)
    sums = "".join(f"{entry['sha256']}  {entry['path']}\n" for entry in manifest["files"])
    if manifest["total_bytes"] != total_bytes or (staging / "SHA256SUMS").read_text() != sums:
        raise ValueError("HF staging inventory totals or checksums do not match")
    return manifest


def prepare_staging(source: Path, staging: Path) -> dict:
    """Copy verified release files and build a separate Space README and inventory."""
    staging.mkdir(parents=True, exist_ok=True)
    if any(staging.iterdir()):
        raise ValueError("HF staging directory must be empty")
    manifest = json.loads((source / "PUBLIC_RELEASE_MANIFEST.json").read_text())
    paths = []
    for entry in manifest["files"]:
        relative = entry["path"]
        parts = PurePosixPath(relative)
        if parts.is_absolute() or ".." in parts.parts or relative in SELF or relative in paths:
            raise ValueError(f"Invalid release path: {relative}")
        original = source / relative
        if original.is_symlink() or not original.resolve().is_relative_to(source.resolve()):
            raise ValueError(f"Invalid release source: {relative}")
        data = original.read_bytes()
        if len(data) != entry["bytes"] or hashlib.sha256(data).hexdigest() != entry["sha256"]:
            raise ValueError(f"Release changed before staging: {relative}")
        target = staging / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
        paths.append(relative)

    settings = (staging / "docs/huggingface_space.md").read_text(encoding="utf-8")
    blocks = re.findall(r"(?ms)^```yaml[ \t]*\n(.*?)^```[ \t]*$", settings)
    if len(blocks) != 1:
        raise ValueError("HF settings must contain exactly one fenced YAML block")
    frontmatter = blocks[0].strip()
    if not frontmatter.startswith("---\n") or not frontmatter.endswith("\n---"):
        raise ValueError("HF settings must include YAML front matter delimiters")
    readme = staging / "README.md"
    body = readme.read_bytes()
    if body.startswith((b"---\n", b"---\r\n")):
        raise ValueError("GitHub README must omit Space YAML front matter")
    readme.write_bytes(frontmatter.encode("utf-8") + b"\n\n" + body)

    entries = []
    for relative in sorted(paths):
        data = (staging / relative).read_bytes()
        entries.append(
            {"path": relative, "bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()}
        )
    staged_manifest = {
        **manifest,
        "files": entries,
        "total_bytes": sum(x["bytes"] for x in entries),
    }
    (staging / "PUBLIC_RELEASE_MANIFEST.json").write_text(
        json.dumps(staged_manifest, indent=2) + "\n", encoding="utf-8", newline="\n"
    )
    (staging / "SHA256SUMS").write_text(
        "".join(f"{entry['sha256']}  {entry['path']}\n" for entry in entries),
        encoding="utf-8",
        newline="\n",
    )
    return verify_staging(staging)


def main() -> None:
    """Refuse public targets and upload the release manifest's exact allowlist."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-id", default="Zipeng365/tomc-agent-memory-demo")
    args = parser.parse_args()
    subprocess.run([sys.executable, str(ROOT / "scripts/security_scan.py")], check=True)
    subprocess.run(
        [sys.executable, str(ROOT / "scripts/release_manifest.py"), "--check"], check=True
    )
    api = HfApi()
    try:
        info = api.repo_info(args.repo_id, repo_type="space")
        if not info.private:
            raise RuntimeError("Refusing upload: target Space is public")
    except RepositoryNotFoundError:
        api.create_repo(args.repo_id, repo_type="space", space_sdk="gradio", private=True)
    info = api.repo_info(args.repo_id, repo_type="space")
    if not info.private:
        raise RuntimeError("Private visibility could not be verified")
    with TemporaryDirectory(prefix="tomc-hf-staging-") as directory:
        staging = Path(directory)
        manifest = prepare_staging(ROOT, staging)
        paths = [entry["path"] for entry in manifest["files"]] + sorted(SELF)
        commit = api.upload_folder(
            repo_id=args.repo_id,
            repo_type="space",
            folder_path=staging,
            allow_patterns=paths,
            parent_commit=info.sha,
            commit_message="Stage verified TOMC memory workbench v0.1.0",
        )
    info = api.repo_info(args.repo_id, repo_type="space")
    if not info.private:
        raise RuntimeError("Unexpected Space visibility after upload")
    receipt = {
        "url": f"https://huggingface.co/spaces/{args.repo_id}",
        "private": info.private,
        "commit": commit.oid,
        "files_uploaded": len(paths),
        "runtime": str(info.runtime.stage) if info.runtime else "unknown",
    }
    (ROOT / "outputs").mkdir(exist_ok=True)
    (ROOT / "outputs/hf_staging_receipt.json").write_text(json.dumps(receipt, indent=2) + "\n")
    print(json.dumps(receipt, indent=2))


if __name__ == "__main__":
    main()
