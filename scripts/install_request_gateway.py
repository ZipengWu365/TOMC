"""Activate an already validated independent TOMC gateway, with exact-byte rollback.

No authentication, models, approval settings or plugin caches are changed. The
service runtime and hidden Startup shortcut must already exist before activation.
Preview is the default. Activation verifies a live loopback health endpoint.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from urllib.request import ProxyHandler, build_opener

import tomlkit
from install_context_workspace import (
    FileChange,
    UpdatePlan,
    _atomic_write,
    _digest,
    _json,
    _read_current,
    _safe_target,
    install,
)

PET_MODULES = (
    "usage_widget_qt.py",
    "context_library_qt.py",
    "analysis_qt.py",
    "analysis.py",
    "categories.py",
    "savings.py",
    "usage.py",
    "request_activity.py",
    "integration_status.py",
    "context_library.py",
    "session_store.py",
    "ui_language.py",
    "macos_ui.py",
    "pricing_qt.py",
    "oasis_qt.py",
    "cost_estimate.py",
    "pet_growth.py",
    "impact_story.py",
    "usage_widget.py",
    "quota.py",
)


def check_health(port):
    opener = build_opener(ProxyHandler({}))
    with opener.open(f"http://127.0.0.1:{port}/health", timeout=3) as response:
        data = json.loads(response.read(4096))
    if data.get("service") != "tomc-gateway" or data.get("ready") is not True:
        raise ValueError("The expected TOMC gateway is not ready")


def plan_activation(home, runtime, port=43187, *, hosts=("codex", "claude")):
    home, runtime = Path(home).resolve(), Path(runtime).resolve()
    if not 1024 <= port <= 65535 or not hosts or set(hosts) - {"codex", "claude"}:
        raise ValueError("Invalid activation selection")
    required = runtime / "src/tomc/request_gateway.py"
    if not required.is_file():
        raise ValueError("The independent gateway runtime is missing")
    changes = []

    def add(relative, data):
        previous = _read_current(_safe_target(home, relative))
        if previous != data:
            changes.append(FileChange(relative, previous, data))

    if "codex" in hosts:
        relative = ".codex/config.toml"
        before = _read_current(_safe_target(home, relative))
        if before is None:
            raise ValueError("An existing Codex configuration is required")
        document = tomlkit.parse(before.decode("utf-8-sig"))
        if document.get("model_provider", "openai") != "openai":
            raise ValueError("This activation supports the existing built-in OpenAI provider only")
        if document.get("profile"):
            raise ValueError("An active profile must be reviewed before automatic activation")
        existing = document.get("openai_base_url")
        target = f"http://127.0.0.1:{port}/codex"
        if existing is not None and existing != target:
            raise ValueError("Preserve the existing custom Codex upstream before activating")
        document["openai_base_url"] = target
        data = tomlkit.dumps(document).encode("utf-8")
        if before.startswith(b"\xef\xbb\xbf"):
            data = b"\xef\xbb\xbf" + data
        add(relative, data)
    if "claude" in hosts:
        relative = ".claude/settings.json"
        before = _read_current(_safe_target(home, relative))
        document = _json(before, "Claude settings") if before else {}
        env = document.setdefault("env", {})
        if not isinstance(env, dict):
            raise ValueError("Claude env must be an object")
        target = f"http://127.0.0.1:{port}/claude"
        if env.get("ANTHROPIC_BASE_URL") not in (None, target):
            raise ValueError("Preserve the existing custom Claude upstream before activating")
        env["ANTHROPIC_BASE_URL"] = target
        env["CLAUDE_CODE_GATEWAY_HINT_HEADERS"] = "1"
        data = (json.dumps(document, ensure_ascii=False, indent=2) + "\n").encode()
        if before and before.startswith(b"\xef\xbb\xbf"):
            data = b"\xef\xbb\xbf" + data
        add(relative, data)
    pet_relative = ".codex/tomc/pet-current/src/tomc"
    if _safe_target(home, pet_relative + "/usage_widget_qt.py").is_file():
        for name in PET_MODULES:
            contents = (runtime / "src/tomc" / name).read_bytes()
            compile(contents, name, "exec", dont_inherit=True)
            add(pet_relative + "/" + name, contents)
    marker = {
        "version": 1,
        "port": port,
        "hosts": list(hosts),
        "runtime": str(runtime),
        "mode": "automatic_request_gateway",
        "requires_client_restart": "codex" in hosts,
        "client_reload": {
            host: "settings_env_hot_reload_supported"
            if host == "claude"
            else "restart_or_new_thread_required"
            for host in hosts
        },
        "existing_sessions_verified": False,
    }
    add(".codex/tomc/gateway-routing.json", (json.dumps(marker, indent=2) + "\n").encode())
    return UpdatePlan(
        home,
        runtime,
        tuple(changes),
        (
            "Existing authentication, models, permissions and other settings are preserved.",
            "Claude Code settings env supports hot reload; verify each existing session from its next observed request.",
            "Already loaded Codex chats retain their endpoint: exit and reopen Codex once, then continue the same chat. New chats load current settings.",
            "Claude Desktop and other host-managed routes may ignore the CLI environment settings.",
            "Unsupported/native compaction requests pass through; shortened contexts may omit details.",
            "Per-session off stops new compilation; Claude may replay an existing signed prefix.",
        ),
    )


def restore(home, receipt_path):
    """Restore only untouched installed files; never overwrite subsequent user edits."""
    home, receipt_path = Path(home).resolve(), Path(receipt_path).resolve()
    archive_root = _safe_target(home, ".codex/tomc/archive")
    if not receipt_path.is_relative_to(archive_root):
        raise ValueError("Receipt must be within the TOMC backup archive")
    receipt = _json(receipt_path.read_bytes(), "Receipt")
    plans = []
    for entry in receipt["changes"]:
        target = _safe_target(home, entry["target"])
        current = _read_current(target)
        if _digest(current) != entry["after_sha256"]:
            raise ValueError("An installed file has changed; automatic rollback refused")
        backup = entry.get("backup")
        original = None
        if backup:
            backup_path = (receipt_path.parent / backup).resolve()
            if not backup_path.is_relative_to(receipt_path.parent):
                raise ValueError("Invalid backup path")
            original = backup_path.read_bytes()
        if _digest(original) != entry["before_sha256"]:
            raise ValueError("Backup integrity check failed")
        plans.append((target, original, entry["after_sha256"]))
    for target, original, expected in reversed(plans):
        if _digest(_read_current(target)) != expected:
            raise ValueError("An installed file changed during rollback; remaining writes refused")
        if original is None:
            target.unlink()
        else:
            _atomic_write(target, original)
    return {"status": "restored", "files": len(plans)}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--home", type=Path, default=Path.home())
    parser.add_argument("--runtime", type=Path)
    parser.add_argument("--port", type=int, default=43187)
    parser.add_argument(
        "--hosts", nargs="+", choices=["codex", "claude"], default=["codex", "claude"]
    )
    parser.add_argument("--activate", action="store_true")
    parser.add_argument("--restore", type=Path)
    args = parser.parse_args(argv)
    if args.restore:
        print(json.dumps(restore(args.home, args.restore)))
        return 0
    if args.runtime is None:
        parser.error("--runtime is required")
    plan = plan_activation(args.home, args.runtime, args.port, hosts=args.hosts)
    print(
        json.dumps(
            {
                "mode": "activate" if args.activate else "preview",
                "files": [c.relative for c in plan.changes],
                "notes": plan.notes,
            },
            indent=2,
        )
    )
    if args.activate:
        check_health(args.port)
        result = install(plan)
        print(json.dumps({"status": result["status"], "receipt": result.get("receipt")}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
