"""Patch named modules of an installed gateway runtime, with backup, health check and rollback.

Preview by default. ``--install`` refuses while recent model requests may still be
streaming, backs up the exact current bytes with SHA-256, import-checks the new
modules with the runtime's own interpreter on a staged copy, replaces the files,
restarts only the supervised ``--serve`` child, then waits for ``/health`` and a new
listener process. Any failure restores the backup and restarts again.
``--rollback BACKUP_DIR`` restores an earlier backup the same way.

Never touches client configuration, credentials, chats, the database or the supervisor.
Windows only (the installed gateway is a per-user Windows service).
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import sqlite3
import subprocess
import tempfile
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.request import ProxyHandler, build_opener

MODULES = ("request_gateway.py", "responses_request.py", "anthropic_request.py", "request_activity.py")


def _sha(path: Path) -> str | None:
    return hashlib.sha256(path.read_bytes()).hexdigest() if path.is_file() else None


def _stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def _powershell(command: str) -> str:
    return subprocess.run(["powershell", "-NoProfile", "-NonInteractive", "-Command", command],
                          capture_output=True, text=True, timeout=60).stdout.strip()


def listener_pid(port: int) -> int | None:
    value = _powershell(f"(Get-NetTCPConnection -LocalAddress 127.0.0.1 -LocalPort {port} -State Listen "
                        "-ErrorAction SilentlyContinue | Select-Object -First 1).OwningProcess")
    return int(value) if value.isdigit() else None


def command_line(pid: int) -> str:
    return _powershell(f'(Get-CimInstance Win32_Process -Filter "ProcessId={int(pid)}").CommandLine')


def healthy(port: int) -> bool:
    try:
        with build_opener(ProxyHandler({})).open(f"http://127.0.0.1:{port}/health", timeout=1) as response:
            data = json.loads(response.read(4096))
        return data.get("service") == "tomc-gateway" and data.get("ready") is True
    except (OSError, ValueError):
        return False


def pending_requests(store: Path, minutes: int = 10) -> int:
    """Requests that were sent recently and have neither usage nor a failure yet."""
    if not store.exists():
        return 0
    cutoff = (datetime.now(timezone.utc) - timedelta(minutes=minutes)).isoformat()
    preparing = (datetime.now(timezone.utc) - timedelta(minutes=2)).isoformat()
    db = sqlite3.connect(store.resolve().as_uri() + "?mode=ro", uri=True, timeout=2)
    try:
        return db.execute(
            "SELECT COUNT(*) FROM tomc_request_activity WHERE "
            "(sent=1 AND state IN ('forwarded','passthrough') AND provider_input_tokens IS NULL "
            "AND started_utc>=?) OR (state='preparing' AND started_utc>=?)", (cutoff, preparing)).fetchone()[0]
    finally:
        db.close()


def import_check(runtime: Path, replacements: dict[str, bytes]) -> None:
    """Import every gateway module from a staged copy using the runtime's interpreter."""
    python = runtime / ".venv/Scripts/python.exe"
    with tempfile.TemporaryDirectory(prefix="tomc-gateway-stage-") as staged:
        package = Path(staged) / "tomc"
        shutil.copytree(runtime / "src/tomc", package, ignore=shutil.ignore_patterns("__pycache__"))
        for name, data in replacements.items():
            (package / name).write_bytes(data)
        names = ", ".join(f"tomc.{Path(name).stem}" for name in MODULES)
        result = subprocess.run([str(python), "-I", "-B", "-c",
                                 f"import sys; sys.path.insert(0, {str(staged)!r}); import {names}"],
                                capture_output=True, text=True, timeout=120)
        if result.returncode != 0:
            raise RuntimeError("Staged import check failed:\n" + result.stderr[-2000:])


def write_atomically(target: Path, data: bytes) -> None:
    temporary = target.with_name(target.name + ".tomc-new")
    temporary.write_bytes(data)
    os.replace(temporary, target)


def restart_service(runtime: Path, port: int, timeout: float = 45) -> dict:
    """Stop only the supervised --serve tree; the supervisor starts a fresh child."""
    status_path = runtime / "config.status.json"
    status = json.loads(status_path.read_text(encoding="utf-8"))
    service = int(status["service_pid"])
    line = command_line(service)
    if "--serve" not in line or str(runtime).lower() not in line.lower():
        raise RuntimeError(f"service_pid {service} is not this runtime's --serve process")
    before_listener = listener_pid(port)
    subprocess.run(["taskkill", "/PID", str(service), "/T", "/F"], capture_output=True, timeout=30)
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        time.sleep(1)
        try:
            current = json.loads(status_path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        listener = listener_pid(port)
        if (int(current.get("service_pid", service)) != service and listener
                and listener != before_listener and healthy(port)):
            return {"previous_service_pid": service, "service_pid": int(current["service_pid"]),
                    "previous_listener_pid": before_listener, "listener_pid": listener}
    raise RuntimeError("The gateway did not come back healthy with a new listener in time")


def apply(runtime: Path, files: dict[str, bytes], label: str) -> dict:
    """Back up, swap, restart; restore and restart again on any failure."""
    config = json.loads((runtime / "config.json").read_text(encoding="utf-8"))
    port = int(config.get("port", 43187))
    package = runtime / "src/tomc"
    backup = runtime / "backups" / f"{label}-{_stamp()}"
    backup.mkdir(parents=True)
    receipt = {"format": "tomc-gateway-module-patch-v1", "created_utc": datetime.now(timezone.utc).isoformat(),
               "runtime": str(runtime), "backup": str(backup), "status": "pending", "modules": []}
    for name, data in files.items():
        current = package / name
        if current.is_file():
            shutil.copyfile(current, backup / name)
        receipt["modules"].append({"module": f"src/tomc/{name}", "before_sha256": _sha(current),
                                   "after_sha256": hashlib.sha256(data).hexdigest(),
                                   "backed_up": current.is_file()})
    receipt_path = backup / "patch-receipt.json"
    receipt_path.write_text(json.dumps(receipt, indent=2), encoding="utf-8")
    try:
        for name, data in files.items():
            write_atomically(package / name, data)
        receipt["restart"] = restart_service(runtime, port)
        receipt["status"] = "running"
    except Exception as error:  # Restore exact bytes, then bring the old code back up.
        receipt["error"] = f"{type(error).__name__}: {error}"[:500]
        for module in receipt["modules"]:
            name = Path(module["module"]).name
            if module["backed_up"]:
                write_atomically(package / name, (backup / name).read_bytes())
            else:
                (package / name).unlink(missing_ok=True)
        try:
            receipt["rollback_restart"] = restart_service(runtime, port)
            receipt["status"] = "rolled_back"
        except Exception as again:
            receipt["status"] = "rollback_restart_failed"
            receipt["rollback_error"] = f"{type(again).__name__}: {again}"[:500]
    receipt["health"] = healthy(port)
    receipt["after_files"] = {name: _sha(package / name) for name in files}
    receipt_path.write_text(json.dumps(receipt, indent=2), encoding="utf-8")
    receipt["receipt"] = str(receipt_path)
    return receipt


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--runtime", type=Path, required=True)
    parser.add_argument("--source", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--module", action="append", help="Module name under src/tomc (default: gateway set)")
    parser.add_argument("--label", default="modules")
    parser.add_argument("--install", action="store_true")
    parser.add_argument("--rollback", type=Path, help="Backup directory written by an earlier --install")
    parser.add_argument("--wait", type=int, default=120, help="Seconds to wait for in-flight requests")
    parser.add_argument("--force", action="store_true", help="Restart even if requests look in flight")
    args = parser.parse_args(argv)
    runtime = args.runtime.resolve()
    if args.rollback:
        backup = args.rollback.resolve()
        receipt = json.loads((backup / "patch-receipt.json").read_text(encoding="utf-8"))
        files = {Path(m["module"]).name: (backup / Path(m["module"]).name).read_bytes()
                 for m in receipt["modules"] if m["backed_up"]}
        label = "rollback"
    else:
        names = args.module or list(MODULES)
        files = {name: (args.source / "src/tomc" / name).read_bytes() for name in names}
        label = args.label
    plan = {name: {"current_sha256": _sha(runtime / "src/tomc" / name),
                   "new_sha256": hashlib.sha256(data).hexdigest()} for name, data in files.items()}
    changed = {name: data for name, data in files.items()
               if plan[name]["current_sha256"] != plan[name]["new_sha256"]}
    print(json.dumps({"mode": "install" if args.install or args.rollback else "preview",
                      "runtime": str(runtime), "changed": sorted(changed), "plan": plan}, indent=2))
    if not (args.install or args.rollback) or not changed:
        return 0
    import_check(runtime, changed)
    store = Path(json.loads((runtime / "config.json").read_text(encoding="utf-8"))["store"])
    deadline = time.monotonic() + max(0, args.wait)
    pending = pending_requests(store)
    while pending and time.monotonic() < deadline and not args.force:
        time.sleep(5)
        pending = pending_requests(store)
    if pending and not args.force:
        print(json.dumps({"status": "not_started", "pending_model_requests": pending}))
        return 3
    result = apply(runtime, changed, label)
    result["pending_model_requests_at_start"] = pending
    print(json.dumps(result, indent=2))
    return 0 if result["status"] == "running" else 4


if __name__ == "__main__":
    raise SystemExit(main())
