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
# Exact, known-fake test fixture values; they are removed before pattern matching.
KNOWN_FIXTURES = (b"Bearer fixture-only-never-a-real-token",)
MAX_RELEASE_BYTES = 5_000_000
HISTORY_SIZE_BASELINE = "scripts/security_history_size_baseline.json"


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


def inspect_blob(data: bytes, label: str, *, enforce_size: bool = True) -> list[str]:
    """Only report category and file/blob label, never matching bytes."""
    scanned = data
    for fixture in KNOWN_FIXTURES:
        scanned = scanned.replace(fixture, b"")
    findings = [f"{label}: {name}" for name, pattern in PATTERNS.items() if pattern.search(scanned)]
    if enforce_size and len(data) > MAX_RELEASE_BYTES:
        findings.append(f"{label}: file larger than 5 MB")
    return findings


def history_size_baseline(root: Path) -> dict[str, dict]:
    """Load exact legacy object sizes; this never exempts credentials or names."""
    path = root / HISTORY_SIZE_BASELINE
    if not path.exists():
        return {}
    payload = json.loads(path.read_text(encoding="utf-8"))
    if payload.get("schema_version") != 1 or not isinstance(
        payload.get("historical_large_blobs"), list
    ):
        raise ValueError("Invalid historical size baseline schema")
    baseline = {}
    for record in payload["historical_large_blobs"]:
        oid = record.get("oid", "")
        size = record.get("bytes")
        old_path = record.get("path", "")
        if (
            not isinstance(oid, str)
            or not re.fullmatch(r"[0-9a-f]{40}", oid)
            or oid in baseline
            or type(size) is not int
            or size <= MAX_RELEASE_BYTES
            or not isinstance(old_path, str)
            or not old_path
            or Path(old_path).is_absolute()
            or ".." in Path(old_path).parts
            or not isinstance(record.get("reason"), str)
            or not record["reason"].strip()
        ):
            raise ValueError("Invalid exact historical size baseline entry")
        baseline[oid] = record
    return baseline


def scan() -> dict:
    """Scan release scope and history; fail closed on unsafe artifacts or credential patterns."""
    findings = []
    paths = candidates(ROOT)
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
    baseline_used = []
    baseline = history_size_baseline(ROOT)
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
            record = baseline.get(oid)
            legacy_size = record is not None and record["bytes"] == len(data)
            findings += inspect_blob(data, f"history:{oid[:12]}", enforce_size=not legacy_size)
            if legacy_size:
                # Free-form provenance stays in the versioned baseline, never
                # echoed here in case a future note accidentally contains a key.
                baseline_used.append({"oid": oid, "bytes": len(data)})
            if FORBIDDEN.search(path) or (
                Path(path).name.startswith(".env") and Path(path).name != ".env.example"
            ):
                findings.append(f"history:{oid[:12]}: excluded artifact")
    result = {
        "status": "pass" if not findings else "fail",
        "files_scanned": len(paths),
        "history_blobs_scanned": history_blobs,
        "history_size_baseline_used": sorted(baseline_used, key=lambda record: record["oid"]),
        "findings": findings,
        "scope": "release files and reachable Git blobs; exact historical size baseline only; "
        "patterns are not proof of absence",
    }
    print(json.dumps(result, indent=2))
    if findings:
        raise SystemExit(1)
    return result


if __name__ == "__main__":
    scan()
