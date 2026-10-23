"""Copy a self-contained, timestamped gateway source runtime; never activate clients."""

import argparse
import hashlib
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path


def stage(source, destination):
    source, destination = Path(source).resolve(), Path(destination).resolve()
    if destination.exists():
        raise ValueError("A gateway runtime must use a new directory")
    package = source / "src/tomc"
    if destination.is_relative_to(package):
        raise ValueError("The destination must not be inside the source package")
    scripts = [source / "scripts" / name for name in (
        "install_request_gateway.py", "install_context_workspace.py", "request_gateway_launcher.pyw")]
    requirements = source / "requirements-gateway.txt"
    if not (package / "request_gateway.py").is_file() or any(
            not path.is_file() for path in [*scripts, requirements]):
        raise ValueError("The gateway source is incomplete")
    files = [path for path in sorted(package.rglob("*")) if path.is_file()
             and not path.is_symlink() and "__pycache__" not in path.parts
             and path.suffix in {".py", ".json"}]
    files += scripts + [requirements]
    destination.mkdir(parents=True, exist_ok=False)
    copied = []
    for path in files:
        relative = path.relative_to(source)
        target = destination / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(path, target)
        copied.append({"path": relative.as_posix(), "sha256": hashlib.sha256(target.read_bytes()).hexdigest()})
    receipt = {"version": "0.1.6-gateway", "created_utc": datetime.now(timezone.utc).isoformat(),
               "files": copied, "clients_activated": False}
    (destination / "source-receipt.json").write_text(json.dumps(receipt, indent=2), encoding="utf-8")
    return {"runtime": str(destination), "files": len(copied), "clients_activated": False}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--destination", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(stage(args.source, args.destination), indent=2))
