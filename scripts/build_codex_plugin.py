"""Build a private Codex marketplace ZIP with the shared locked TOMC runtime."""

from __future__ import annotations

import argparse
import hashlib
import json
import tempfile
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile, ZipInfo

from build_plugin import build_bundle
from security_scan import ROOT, inspect_blob


def build_codex_bundle(destination: Path, root: Path = ROOT) -> dict:
    """Reuse the scanned runtime; add Codex metadata, installer and a focused skill."""
    template = root / "plugins" / "codex"
    metadata = json.loads((template / ".codex-plugin/plugin.json").read_text(encoding="utf-8"))
    prefix = "plugins/tomc-memory/"
    entries = {}
    with tempfile.TemporaryDirectory(prefix="tomc-runtime-") as folder:
        runtime = build_bundle(Path(folder), root)
        with ZipFile(Path(folder) / runtime["artifact"]) as archive:
            for name in archive.namelist():
                if name.startswith("src/") or name in {"pyproject.toml", "uv.lock", "LICENSE"}:
                    entries[prefix + name] = archive.read(name)
    files = {
        ".agents/plugins/marketplace.json": template / "marketplace.json",
        "README.md": template / "README.md",
        "install.py": template / "install.py",
        prefix + ".codex-plugin/plugin.json": template / ".codex-plugin/plugin.json",
        prefix + "mcp.json": template / "mcp.json",
        prefix + "skills/tomc-memory/SKILL.md": template / "skills/tomc-memory/SKILL.md",
    }
    for name, source in files.items():
        if source.is_symlink() or not source.is_file():
            raise ValueError(f"Bundle source must be a regular file: {name}")
        data = source.read_bytes()
        if inspect_blob(data, name):
            raise ValueError(f"Bundle source failed release scan: {name}")
        entries[name] = data
    destination.mkdir(parents=True, exist_ok=True)
    output = destination / f"tomc-memory-codex-{metadata['version']}.zip"
    with ZipFile(output, "w", compression=ZIP_DEFLATED) as archive:
        for name, data in sorted(entries.items()):
            item = ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
            # Match published Windows bundles independently of the build host.
            item.create_system = 0
            item.compress_type = ZIP_DEFLATED
            item.external_attr = 0o100644 << 16
            archive.writestr(item, data)
    receipt = {
        "artifact": output.name,
        "bytes": output.stat().st_size,
        "sha256": hashlib.sha256(output.read_bytes()).hexdigest(),
        "files": len(entries),
        "runtime": "Codex native plugin; UV is required on PATH or supplied with --uv",
        "status": "private candidate; no public directory or model-driven acceptance",
    }
    (destination / (output.name + ".sha256")).write_text(
        f"{receipt['sha256']}  {output.name}\n", encoding="utf-8", newline="\n"
    )
    (destination / "codex_build_receipt.json").write_text(
        json.dumps(receipt, indent=2) + "\n", encoding="utf-8"
    )
    return receipt


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=ROOT / "outputs" / "plugins")
    args = parser.parse_args()
    print(json.dumps(build_codex_bundle(args.output), indent=2))
