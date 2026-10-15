"""Scan distributable files and all reachable Git blobs without printing matched secrets."""

from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SKIP = {
    ".git",
    ".venv",
    "__pycache__",
    ".pytest_cache",
    ".ruff_cache",
    "dist",
    "build",
    "site",
    "outputs",
}
FORBIDDEN = re.compile(
    r"(?:rednoteAPI\.md|reader_jobs\.private|judge_jobs\..*private|reader_results|judge_results|FormalMATH|TheoremBench|MA-ProofBench|UNSAFE_STAGING|INTERIM_DO_NOT_SHARE)",
    re.I,
)
PATTERNS = {
    "credential_token": re.compile(
        rb"(?:gh[pousr]_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{35,}|hf_[A-Za-z0-9]{25,}|sk-[A-Za-z0-9_-]{24,})"
    ),
    "bearer_literal": re.compile(rb"Bearer\s+[A-Za-z0-9_.-]{25,}", re.I),
    "private_key": re.compile(rb"-----BEGIN (?:RSA |OPENSSH |EC )?PRIVATE KEY-----"),
    "credential_assignment": re.compile(
        rb"(?im)^[ \t]*(?:export[ \t]+)?(?:TOMC_READER_API_KEY|OPENAI_API_KEY|HF_TOKEN|GITHUB_TOKEN|DEEPSEEK_API_KEY)[ \t]*=[ \t]*['\"]?[^\s'\"#][^\r\n]{10,}$"
    ),
}


def candidates(root: Path = ROOT) -> list[Path]:
    """Use Git's tracked/unignored inventory; support source distributions without .git."""
    if (root / ".git").is_dir():
        result = subprocess.run(
            ["git", "ls-files", "--cached", "--others", "--exclude-standard", "-z"],
            cwd=root,
            check=True,
            capture_output=True,
        )
        return sorted({root / p.decode() for p in result.stdout.split(b"\0") if p})
    return sorted(
        p for p in root.rglob("*") if p.is_file() and not set(p.relative_to(root).parts) & SKIP
    )


def inspect_blob(data: bytes, label: str) -> list[str]:
    """Only report category and file/blob label, never matching bytes."""
    findings = [f"{label}: {name}" for name, pattern in PATTERNS.items() if pattern.search(data)]
    if len(data) > 5_000_000:
        findings.append(f"{label}: file larger than 5 MB")
    return findings


def scan() -> dict:
    """Scan release scope and history; fail closed on unsafe artifacts or credential patterns."""
    findings = []
    paths = candidates()
    for path in paths:
        relative = str(path.relative_to(ROOT))
        if path.is_symlink():
            findings.append(f"{relative}: symlink is not allowed in release")
        if FORBIDDEN.search(relative) or (
            path.name.startswith(".env") and path.name != ".env.example"
        ):
            findings.append(f"{relative}: excluded artifact name")
        if path.is_file():
            findings += inspect_blob(path.read_bytes(), relative)
    history_blobs = 0
    if (ROOT / ".git").is_dir():
        result = subprocess.run(
            ["git", "rev-list", "--objects", "--all"],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=True,
        )
        for line in result.stdout.splitlines():
            oid, _, path = line.partition(" ")
            kind = subprocess.run(
                ["git", "cat-file", "-t", oid], cwd=ROOT, capture_output=True, text=True, check=True
            ).stdout.strip()
            if kind != "blob":
                continue
            history_blobs += 1
            data = subprocess.run(
                ["git", "cat-file", "blob", oid], cwd=ROOT, capture_output=True, check=True
            ).stdout
            findings += inspect_blob(data, f"history:{oid[:12]}")
            if FORBIDDEN.search(path) or (
                Path(path).name.startswith(".env") and Path(path).name != ".env.example"
            ):
                findings.append(f"history:{oid[:12]}: excluded artifact")
    result = {
        "status": "pass" if not findings else "fail",
        "files_scanned": len(paths),
        "history_blobs_scanned": history_blobs,
        "findings": findings,
        "scope": "release files and reachable Git blobs; patterns are not proof of absence",
    }
    print(json.dumps(result, indent=2))
    if findings:
        raise SystemExit(1)
    return result


if __name__ == "__main__":
    scan()
