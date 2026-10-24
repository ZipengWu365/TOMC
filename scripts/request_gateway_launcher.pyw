"""Hidden per-user gateway supervisor. Only process status is written, never requests."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path


def supervise(runtime, config):
    """Keep one child alive and clean it up if supervisor bookkeeping fails."""
    child = None
    try:
        while True:
            child = subprocess.Popen(
                [sys.executable, str(Path(__file__).resolve()), "--runtime", str(runtime),
                 "--config", str(config), "--serve"],
                cwd=runtime, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
            state = {"supervisor_pid": os.getpid(), "service_pid": child.pid,
                     "started_utc": datetime.now(timezone.utc).isoformat(),
                     "runtime": str(runtime), "config": str(config)}
            temporary = config.with_suffix(".status.tmp")
            temporary.write_text(json.dumps(state, indent=2), encoding="utf-8")
            os.replace(temporary, config.with_suffix(".status.json"))
            child.wait()
            child = None
            time.sleep(3)
    finally:
        if child is not None and child.poll() is None:
            child.terminate()
            try:
                child.wait(timeout=5)
            except subprocess.TimeoutExpired:
                child.kill()
                child.wait(timeout=5)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--runtime", type=Path, required=True)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--serve", action="store_true")
    args = parser.parse_args()
    runtime, config = args.runtime.resolve(), args.config.resolve()
    if args.serve:
        sys.path.insert(0, str(runtime / "src"))
        from tomc.request_gateway import main as serve
        serve(["--config", str(config)])
        return
    # One supervisor owns this configuration across Startup and manual launch.
    import msvcrt
    lock_path = config.with_suffix(".lock")
    with lock_path.open("a+b") as lock:
        lock.seek(0)
        if not lock.read(1):
            lock.write(b"0")
            lock.flush()
        lock.seek(0)
        try:
            msvcrt.locking(lock.fileno(), msvcrt.LK_NBLCK, 1)
        except OSError:
            return
        try:
            supervise(runtime, config)
        finally:
            lock.seek(0)
            msvcrt.locking(lock.fileno(), msvcrt.LK_UNLCK, 1)


if __name__ == "__main__":
    main()
