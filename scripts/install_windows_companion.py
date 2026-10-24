"""Install the TOMC desktop companion on Windows from this source checkout.

Preview is the default: the plan is printed and nothing changes. --install
creates the companion's own Python environment, copies this checkout's TOMC
source into it, adds Start menu and sign-in shortcuts and starts the cat.
--gateway also sets up the local request gateway and points Codex and/or
Claude Code at it, keeping exact-byte backups. --uninstall RECEIPT undoes an
installation. Saved contexts and statistics in ~/.tomc are never removed.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.request import ProxyHandler, build_opener

ROOT = Path(__file__).resolve().parents[1]
WIDGET = "PySide6-Essentials>=6.8,<7"
PORT = 43187
HOSTS = ("codex", "claude")
# The validated upstreams: Codex signed in with ChatGPT, and Anthropic's API for Claude Code.
UPSTREAMS = {
    "codex": "https://chatgpt.com/backend-api/codex",
    "claude": "https://api.anthropic.com",
}
RECENT_MESSAGES = {"codex": 6, "claude": 1}
CAT_SHORTCUT, MENU_SHORTCUT, GATEWAY_SHORTCUT = "TOMC Cat.lnk", "TOMC.lnk", "TOMC Gateway.lnk"


def version():
    text = (ROOT / "src/tomc/__init__.py").read_text(encoding="utf-8")
    return re.search(r'__version__ = "([^"]+)"', text).group(1)


def stamp():
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


class Layout:
    """Where the companion lives; the defaults match existing installations and updaters."""

    def __init__(self, home, startup, programs):
        self.home = Path(home).resolve()
        self.base = self.home / ".codex" / "tomc"
        # The name predates the cat; update_pet_ui.py and older installs expect it.
        self.env = self.base / "hourglass-ui"
        self.runtime = self.base / "pet-current"
        self.launcher = self.base / "pet.pyw"
        self.icon = self.base / "pet.ico"
        self.startup = Path(startup)
        self.programs = Path(programs)
        self.routing = self.base / "gateway-routing.json"

    @property
    def python(self):
        return self.env / "Scripts" / "python.exe"

    @property
    def pythonw(self):
        return self.env / "Scripts" / "pythonw.exe"


# Windows helpers ----------------------------------------------------------------


def powershell(script, **values):
    """Run a short PowerShell script. Values arrive as TOMC_* variables, never quoted inline."""
    env = {**os.environ, **{f"TOMC_{key.upper()}": str(value) for key, value in values.items()}}
    result = subprocess.run(
        [
            "powershell",
            "-NoProfile",
            "-NonInteractive",
            "-ExecutionPolicy",
            "Bypass",
            "-Command",
            "[Console]::OutputEncoding=[Text.Encoding]::UTF8;" + script,
        ],
        env=env,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=120,
    )
    if result.returncode:
        raise RuntimeError(result.stderr.strip() or "PowerShell failed")
    return result.stdout.strip()


def known_folder(name):
    return Path(powershell(f"[Environment]::GetFolderPath('{name}')"))


def write_shortcut(path, target, arguments, folder, description, icon=None):
    powershell(
        "$l=(New-Object -ComObject WScript.Shell).CreateShortcut($env:TOMC_PATH);"
        "$l.TargetPath=$env:TOMC_TARGET;$l.Arguments=$env:TOMC_ARGUMENTS;"
        "$l.WorkingDirectory=$env:TOMC_FOLDER;$l.Description=$env:TOMC_DESCRIPTION;"
        "if($env:TOMC_ICON){$l.IconLocation=$env:TOMC_ICON};$l.WindowStyle=7;$l.Save()",
        path=path,
        target=target,
        arguments=arguments,
        folder=folder,
        description=description,
        icon=icon or "",
    )
    written = read_shortcut(path)
    if (written["target"].lower(), written["arguments"]) != (str(target).lower(), arguments):
        raise RuntimeError(f"Shortcut verification failed: {path}")


def read_shortcut(path):
    data = powershell(
        "$l=(New-Object -ComObject WScript.Shell).CreateShortcut($env:TOMC_PATH);"
        "@{target=$l.TargetPath;arguments=$l.Arguments}|ConvertTo-Json -Compress",
        path=path,
    )
    return json.loads(data)


def processes():
    data = powershell(
        "Get-CimInstance Win32_Process -Filter \"Name='pythonw.exe' OR Name='python.exe'\" | "
        "Select-Object ProcessId,CommandLine | ConvertTo-Json -Compress"
    )
    rows = json.loads(data) if data else []
    return [rows] if isinstance(rows, dict) else rows


def stop_processes(fragment):
    """Stop only processes whose command line names this installation's own files."""
    stopped = []
    for row in processes():
        if str(fragment).lower() in (row.get("CommandLine") or "").lower():
            subprocess.run(
                ["taskkill", "/PID", str(row["ProcessId"]), "/T", "/F"], capture_output=True
            )
            stopped.append(row["ProcessId"])
    return stopped


def start(shortcut):
    # Started by the Windows shell, so it outlives the terminal that ran the installer.
    subprocess.Popen(["explorer.exe", str(shortcut)])


def run(command, **kwargs):
    result = subprocess.run(
        [str(part) for part in command],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        **kwargs,
    )
    if result.returncode:
        detail = (result.stderr or result.stdout).strip().splitlines()[-5:]
        raise RuntimeError(f"{Path(command[0]).name} failed: " + " | ".join(detail))
    return result.stdout


def create_env(path, requirements):
    """A private virtual environment; pip downloads the listed packages."""
    if not (path / "Scripts" / "python.exe").is_file():
        run([sys.executable, "-m", "venv", path])
    run(
        [
            path / "Scripts" / "python.exe",
            "-m",
            "pip",
            "install",
            "--disable-pip-version-check",
            "--upgrade",
            *requirements,
        ]
    )


def make_icon(layout):
    """Best effort: a Start menu icon from the cat head, using the Qt just installed."""
    source = layout.runtime / "src/tomc/data/tomc-expression-1.png"
    code = (
        "import sys\nfrom PySide6.QtGui import QGuiApplication, QImage\n"
        "from PySide6.QtCore import Qt\napp = QGuiApplication([])\n"
        "image = QImage(sys.argv[1]).scaled(256, 256, Qt.AspectRatioMode.KeepAspectRatio, "
        "Qt.TransformationMode.SmoothTransformation)\n"
        "sys.exit(0 if image.save(sys.argv[2], 'ICO') else 1)\n"
    )
    try:
        run(
            [layout.python, "-c", code, source, layout.icon],
            env={**os.environ, "QT_QPA_PLATFORM": "offscreen"},
        )
        return layout.icon.is_file()
    except (RuntimeError, OSError):
        return False


def wait_healthy(port, seconds=45):
    opener = build_opener(ProxyHandler({}))
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        try:
            with opener.open(f"http://127.0.0.1:{port}/health", timeout=3) as response:
                data = json.loads(response.read(4096))
            if data.get("service") == "tomc-gateway" and data.get("ready") is True:
                return True
        except (OSError, ValueError):
            pass
        time.sleep(1)
    return False


# Plan ---------------------------------------------------------------------------


def gateway_config(layout, port):
    return {
        "port": port,
        "store": str(layout.home / ".tomc" / "memory.sqlite3"),
        "routes": {
            host: {
                "upstream": UPSTREAMS[host],
                "compression": {"recent_messages": RECENT_MESSAGES[host]},
            }
            for host in HOSTS
        },
    }


def gateway_problems(layout, hosts):
    """Checks that need no third-party package; activation repeats them exactly."""
    problems = []
    if layout.routing.exists():
        problems.append(
            "A TOMC gateway is already set up on this computer; update it with "
            "scripts/patch_gateway_runtime.py instead."
        )
    codex = layout.home / ".codex" / "config.toml"
    if "codex" in hosts:
        if not codex.is_file():
            problems.append(
                "Codex has no ~/.codex/config.toml yet: open Codex and sign in once first."
            )
        else:
            settings = top_level_toml(codex.read_text(encoding="utf-8-sig"))
            if settings.get("openai_base_url"):
                problems.append(
                    "Codex already uses a custom endpoint (openai_base_url); it is kept."
                )
            if settings.get("model_provider", "openai") != "openai" or settings.get("profile"):
                problems.append(
                    "Codex uses another model provider or an active profile; route it by hand."
                )
    claude = layout.home / ".claude" / "settings.json"
    if "claude" in hosts and claude.is_file():
        try:
            env = json.loads(claude.read_text(encoding="utf-8-sig")).get("env") or {}
        except (ValueError, AttributeError):
            env = {"ANTHROPIC_BASE_URL": "unreadable"}
        if not isinstance(env, dict) or env.get("ANTHROPIC_BASE_URL"):
            problems.append(
                "Claude Code already uses a custom endpoint (ANTHROPIC_BASE_URL); it is kept."
            )
    return problems


def top_level_toml(text):
    """The few top-level string settings checked here, without a TOML package on Python 3.10."""
    settings = {}
    for line in text.splitlines():
        if line.lstrip().startswith("["):
            break
        match = re.match(r'\s*([A-Za-z_][\w-]*)\s*=\s*"([^"]*)"', line)
        if match:
            settings[match.group(1)] = match.group(2)
    return settings


def plan(layout, *, gateway=False, hosts=HOSTS, port=PORT):
    reuse_env = layout.python.is_file()
    actions = {
        "mode": "preview",
        "version": version(),
        "python": sys.executable,
        "environment": {
            "path": str(layout.env),
            "action": "reuse and update" if reuse_env else "create",
            "packages": [WIDGET],
        },
        "runtime": {
            "path": str(layout.runtime),
            "action": "replace (old copy kept in the archive)"
            if layout.runtime.exists()
            else "create",
        },
        "launcher": str(layout.launcher),
        "shortcuts": [str(layout.programs / MENU_SHORTCUT), str(layout.startup / CAT_SHORTCUT)],
        "data": str(layout.home / ".tomc"),
        "data_kept": True,
        "gateway": {"selected": gateway},
    }
    if gateway:
        actions["gateway"].update(
            {
                "hosts": list(hosts),
                "port": port,
                "upstreams": {host: UPSTREAMS[host] for host in hosts},
                "shortcut": str(layout.startup / GATEWAY_SHORTCUT),
                "changes_host_settings": [
                    *([".codex/config.toml: openai_base_url"] if "codex" in hosts else []),
                    *(
                        [".claude/settings.json: env.ANTHROPIC_BASE_URL"]
                        if "claude" in hosts
                        else []
                    ),
                ],
                "problems": gateway_problems(layout, hosts),
            }
        )
    return actions


# Install ------------------------------------------------------------------------


class Receipt:
    def __init__(self, layout):
        self.layout = layout
        self.folder = layout.base / "archive" / f"windows-install-{stamp()}"
        self.data = {
            "kind": "tomc-windows-install",
            "version": version(),
            "source": str(ROOT),
            "installed_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "home": str(layout.home),
            "created": [],
            "replaced": {},
            "gateway": None,
        }

    @property
    def path(self):
        return self.folder / "receipt.json"

    def keep(self, path):
        """Move an existing file or folder into the archive before it is replaced."""
        path = Path(path)
        if not path.exists():
            self.data["created"].append(str(path))
            return
        backup = self.folder / "backup" / str(len(self.data["replaced"]))
        backup.parent.mkdir(parents=True, exist_ok=True)
        if path.is_dir():
            shutil.move(str(path), str(backup))
        else:
            shutil.copy2(path, backup)
        self.data["replaced"][str(path)] = str(backup)

    def save(self):
        self.folder.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(self.data, indent=2), encoding="utf-8")


def install_cat(layout, receipt, *, start_after=True):
    layout.base.mkdir(parents=True, exist_ok=True)
    created_env = not layout.python.is_file()
    create_env(layout.env, [WIDGET])
    if created_env:
        receipt.data["created"].append(str(layout.env))
    stop_processes(layout.launcher)
    receipt.keep(layout.runtime)
    shutil.copytree(
        ROOT / "src/tomc",
        layout.runtime / "src/tomc",
        ignore=shutil.ignore_patterns("__pycache__", "*.pyc"),
    )
    (layout.runtime / "scripts").mkdir(parents=True, exist_ok=True)
    shutil.copy2(ROOT / "scripts/desktop_pet_evolution.py", layout.runtime / "scripts")
    (layout.runtime / "CURRENT.json").write_text(
        json.dumps(
            {"version": version(), "installed_utc": receipt.data["installed_utc"]}, indent=2
        ),
        encoding="utf-8",
    )
    receipt.keep(layout.launcher)
    shutil.copy2(ROOT / "scripts/pet_launcher.pyw", layout.launcher)
    receipt.keep(layout.icon)
    receipt.save()
    icon = layout.icon if make_icon(layout) else None
    arguments = f'"{layout.launcher}"'
    for folder, name, text in (
        (layout.programs, MENU_SHORTCUT, "TOMC desktop companion"),
        (layout.startup, CAT_SHORTCUT, "Start the TOMC desktop companion at Windows sign-in."),
    ):
        folder.mkdir(parents=True, exist_ok=True)
        receipt.keep(folder / name)
        write_shortcut(folder / name, layout.pythonw, arguments, layout.base, text, icon)
    receipt.save()
    if start_after:
        start(layout.programs / MENU_SHORTCUT)


def install_gateway(layout, receipt, *, hosts, port, start_after=True):
    sys.path.insert(0, str(ROOT / "scripts"))
    from stage_request_gateway import stage

    runtime = layout.base / f"gateway-{version()}-{stamp()}"
    stage(ROOT, runtime)
    gateway = {"runtime": str(runtime), "hosts": list(hosts), "port": port, "activation": None}
    receipt.data["gateway"] = gateway
    receipt.save()
    create_env(runtime / ".venv", ["-r", runtime / "requirements-gateway.txt"])
    config = runtime / "config.json"
    config.write_text(json.dumps(gateway_config(layout, port), indent=2), encoding="utf-8")
    python = runtime / ".venv" / "Scripts" / "python.exe"
    tool = [
        python,
        ROOT / "scripts/install_request_gateway.py",
        "--home",
        layout.home,
        "--runtime",
        runtime,
        "--port",
        port,
        "--hosts",
        *hosts,
    ]
    run(tool)  # the exact activation checks, before anything else changes
    shortcut = layout.startup / GATEWAY_SHORTCUT
    shortcut.parent.mkdir(parents=True, exist_ok=True)
    receipt.keep(shortcut)
    write_shortcut(
        shortcut,
        runtime / ".venv" / "Scripts" / "pythonw.exe",
        f'"{runtime / "scripts" / "request_gateway_launcher.pyw"}" --runtime "{runtime}" --config "{config}"',
        runtime,
        "Start the local TOMC request gateway at Windows sign-in.",
    )
    receipt.save()
    if not start_after:
        return gateway
    start(shortcut)
    if not wait_healthy(port):
        raise RuntimeError(
            f"The gateway did not answer on 127.0.0.1:{port}; host settings were not changed."
        )
    output = run([*tool, "--activate"])
    match = re.search(r'"receipt":\s*"((?:[^"\\]|\\.)*)"', output)
    gateway["activation"] = json.loads(f'"{match.group(1)}"') if match else None
    receipt.save()
    return gateway


# Uninstall ----------------------------------------------------------------------


def uninstall(layout, receipt_path):
    receipt_path = Path(receipt_path).resolve()
    if not receipt_path.is_relative_to(layout.base / "archive"):
        raise ValueError("Use a receipt from this installation's archive folder.")
    data = json.loads(receipt_path.read_text(encoding="utf-8"))
    if data.get("kind") != "tomc-windows-install":
        raise ValueError("This is not a TOMC Windows installation receipt.")
    report = {"restored": [], "removed": [], "stopped": []}
    gateway = data.get("gateway")
    if gateway:
        runtime = Path(gateway["runtime"])
        if gateway.get("activation"):
            run(
                [
                    runtime / ".venv/Scripts/python.exe",
                    ROOT / "scripts/install_request_gateway.py",
                    "--home",
                    layout.home,
                    "--restore",
                    gateway["activation"],
                ]
            )
            report["restored"].append("host settings")
        report["stopped"] += stop_processes(runtime)
    report["stopped"] += stop_processes(layout.launcher)
    time.sleep(1)
    for path, backup in reversed(list(data["replaced"].items())):
        path, backup = Path(path), Path(backup)
        if path.is_dir():
            shutil.rmtree(path)
        elif path.exists():
            path.unlink()
        if backup.is_dir():
            shutil.move(str(backup), str(path))
        else:
            shutil.copy2(backup, path)
        report["restored"].append(str(path))
    for path in map(Path, reversed(data["created"])):
        if path.is_dir():
            shutil.rmtree(path, ignore_errors=True)
        elif path.exists():
            path.unlink()
        report["removed"].append(str(path))
    if gateway:
        shutil.rmtree(gateway["runtime"], ignore_errors=True)
        report["removed"].append(gateway["runtime"])
    report["data_kept"] = str(layout.home / ".tomc")
    return report


# Command line -------------------------------------------------------------------


def main(argv=None):
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--install", action="store_true", help="apply the plan")
    parser.add_argument(
        "--gateway", action="store_true", help="also set up automatic request processing"
    )
    parser.add_argument("--hosts", nargs="+", choices=HOSTS, default=list(HOSTS))
    parser.add_argument("--port", type=int, default=PORT)
    parser.add_argument("--no-start", action="store_true", help="install without starting anything")
    parser.add_argument("--uninstall", type=Path, metavar="RECEIPT")
    # Folders below are for tests and unusual setups; the defaults are the real ones.
    parser.add_argument("--home", type=Path, default=Path.home(), help=argparse.SUPPRESS)
    parser.add_argument("--startup", type=Path, help=argparse.SUPPRESS)
    parser.add_argument("--programs", type=Path, help=argparse.SUPPRESS)
    args = parser.parse_args(argv)
    if os.name != "nt":
        parser.error("This installer is for Windows; on macOS use scripts/install_macos_pet.py.")
    if sys.version_info < (3, 10):
        parser.error("Python 3.10 or newer is required.")
    layout = Layout(
        args.home,
        args.startup or known_folder("Startup"),
        args.programs or known_folder("Programs"),
    )
    if args.uninstall:
        try:
            print(json.dumps(uninstall(layout, args.uninstall), indent=2))
        except (RuntimeError, ValueError, OSError) as error:
            # Host settings are restored first, so a gateway they still name keeps serving them.
            print(json.dumps({"status": "stopped", "reason": str(error)}, indent=2))
            return 2
        return 0
    actions = plan(layout, gateway=args.gateway, hosts=tuple(args.hosts), port=args.port)
    problems = actions["gateway"].get("problems") or []
    if not args.install:
        print(json.dumps(actions, indent=2))
        print("\nNothing was changed. Add --install to apply.", file=sys.stderr)
        return 0
    if problems:
        print(json.dumps({"status": "refused", "problems": problems}, indent=2))
        return 2
    receipt = Receipt(layout)
    receipt.save()
    try:
        install_cat(layout, receipt, start_after=not args.no_start)
        if args.gateway:
            install_gateway(
                layout,
                receipt,
                hosts=tuple(args.hosts),
                port=args.port,
                start_after=not args.no_start,
            )
    except Exception as error:
        receipt.save()
        print(
            json.dumps(
                {
                    "status": "failed",
                    "error": str(error),
                    "receipt": str(receipt.path),
                    "undo": f'python {Path(__file__).name} --uninstall "{receipt.path}"',
                },
                indent=2,
            )
        )
        return 1
    result = {"status": "installed", "receipt": str(receipt.path), "version": version()}
    if args.gateway:
        result["next"] = "Quit and reopen Codex and Claude Code so new requests go through TOMC."
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
