"""Build a small, deterministic MCPB from source; never include local notebooks."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile, ZipInfo

from security_scan import ROOT, inspect_blob


def build_bundle(destination: Path, root: Path = ROOT) -> dict:
    """Package the template and allowlisted core source, not the checkout or a venv."""
    template = root / "plugins" / "claude"
    manifest = json.loads((template / "manifest.json").read_text(encoding="utf-8"))
    files = {
        "manifest.json": template / "manifest.json",
        "pyproject.toml": template / "pyproject.toml",
        "uv.lock": template / "uv.lock",
        "README.md": template / "README.md",
        "src/server.py": template / "src/server.py",
        "LICENSE": root / "LICENSE",
    }
    core = root / "src" / "tomc"
    for path in core.rglob("*"):
        if path.suffix == ".py" or (path.suffix == ".json" and path.parent == core / "data"):
            files["src/tomc/" + path.relative_to(core).as_posix()] = path
    entries = {}
    for name, source in sorted(files.items()):
        if source.is_symlink() or not source.is_file():
            raise ValueError(f"Bundle source must be a regular file: {name}")
        data = source.read_bytes()
        if inspect_blob(data, name):
            raise ValueError(f"Bundle source failed release scan: {name}")
        entries[name] = data
    destination.mkdir(parents=True, exist_ok=True)
    output = destination / f"tomc-memory-{manifest['version']}.mcpb"
    with ZipFile(output, "w", compression=ZIP_DEFLATED) as archive:
        for name, data in entries.items():
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
        "runtime": "MCPB 0.4 UV; first installation downloads Python and dependencies",
        "status": "private installation candidate; desktop GUI acceptance pending",
    }
    (destination / (output.name + ".sha256")).write_text(
        f"{receipt['sha256']}  {output.name}\n", encoding="utf-8", newline="\n"
    )
    (destination / "build_receipt.json").write_text(
        json.dumps(receipt, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return receipt


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=ROOT / "outputs" / "plugins")
    args = parser.parse_args()
    print(json.dumps(build_bundle(args.output), ensure_ascii=False, indent=2))
