"""Space packaging keeps SDK metadata and hashes the bytes that will be uploaded."""

import hashlib
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


def test_space_staging_preserves_configuration_and_verifies_upload_bytes(tmp_path, monkeypatch):
    monkeypatch.syspath_prepend(str(ROOT / "scripts"))
    from stage_hf import prepare_staging, verify_staging

    source = tmp_path / "source"
    source.mkdir()
    paths = ["README.md", "docs/huggingface_space.md"]
    entries = []
    for relative in paths:
        data = (ROOT / relative).read_bytes()
        target = source / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
        entries.append(
            {"path": relative, "bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()}
        )
    manifest = {
        "schema": "tomc-public-release-v1",
        "files": entries,
        "total_bytes": sum(entry["bytes"] for entry in entries),
        "self_excluded": ["PUBLIC_RELEASE_MANIFEST.json", "SHA256SUMS"],
    }
    manifest_path = source / "PUBLIC_RELEASE_MANIFEST.json"
    original_manifest = json.dumps(manifest).encode()
    manifest_path.write_bytes(original_manifest)
    (source / "unlisted.txt").write_text("Excluded from the release inventory.")
    original_readme = (source / "README.md").read_bytes()

    staged = tmp_path / "staged"
    result = prepare_staging(source, staged)

    readme = (staged / "README.md").read_bytes()
    header, body = readme.decode("utf-8").split("\n---\n\n", 1)
    assert header.startswith("---\n")
    fields = dict(line.split(": ", 1) for line in header.removeprefix("---\n").splitlines())
    assert fields["sdk"] == "gradio"
    assert fields["sdk_version"] == "5.49.1"
    assert fields["python_version"].strip("'\"") == "3.10"
    assert fields["app_file"] == "app.py"
    assert body.encode("utf-8") == original_readme
    assert not original_readme.startswith((b"---\n", b"---\r\n"))
    assert (source / "README.md").read_bytes() == original_readme
    assert manifest_path.read_bytes() == original_manifest
    assert not (staged / "unlisted.txt").exists()
    readme_entry = next(entry for entry in result["files"] if entry["path"] == "README.md")
    assert readme_entry["bytes"] == len(readme)
    assert readme_entry["sha256"] == hashlib.sha256(readme).hexdigest()
    assert verify_staging(staged) == result

    (staged / "README.md").write_bytes(readme + b"Changed after packaging.")
    with pytest.raises(ValueError, match="HF staging hash mismatch: README.md"):
        verify_staging(staged)
