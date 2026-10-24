"""Build a local macOS TOMC.app using this Python environment and source checkout.

Run with the Python that has tomc-memory[widget] installed. The app embeds that
Python in its own native process; it is not a redistributable, self-contained app.
Keep this checkout, the Python installation and its environment in place. This
does not launch the pet, configure login startup, or change host/gateway settings.
Existing TOMC apps require --replace and are retained as timestamped backups.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import os
import platform
import plistlib
import shlex
import shutil
import subprocess
import sys
import sysconfig
import tempfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BUNDLE_ID = "com.tomc.desktop-pet"
CHECK_ARGUMENT = "--tomc-launcher-check"


@dataclass(frozen=True)
class Runtime:
    executable: Path
    home: Path
    prefix: Path
    source: Path
    package_paths: tuple[Path, ...]
    include: Path
    library: Path
    clang: str
    architecture: str


def checked_run(command: list[str]) -> subprocess.CompletedProcess:
    result = subprocess.run(command, capture_output=True, text=True, check=False)
    if result.returncode:
        detail = (result.stderr or result.stdout).strip()
        raise ValueError(f"Command failed ({command[0]}): {detail}")
    return result


def discover_runtime() -> Runtime:
    """Validate dependencies before creating or replacing the destination app."""
    if sys.platform != "darwin":
        raise ValueError("This installer must run on macOS.")
    if sys.version_info < (3, 10):
        raise ValueError("TOMC needs Python 3.10 or newer.")
    clang = shutil.which("clang")
    if not clang:
        raise ValueError("clang is required. Install Apple's Command Line Tools first.")
    checked_run([clang, "--version"])
    include = Path(sysconfig.get_path("include"))
    if not (include / "Python.h").is_file():
        raise ValueError(f"Python development headers are missing: {include / 'Python.h'}")
    library_name = sysconfig.get_config_var("LDLIBRARY")
    library_dir = sysconfig.get_config_var("LIBDIR")
    if not library_name or not library_dir:
        raise ValueError("This Python does not expose a shared library through sysconfig.")
    library = Path(library_dir) / library_name
    if not library.is_file() or library.suffix not in {".dylib", ""}:
        raise ValueError(f"A shared Python dylib/framework is required: {library}")
    source = ROOT / "src"
    if not (source / "tomc/usage_widget.py").is_file():
        raise ValueError("Keep this installer in the TOMC source checkout's scripts directory.")
    package_paths = []
    for name in ("purelib", "platlib"):
        candidate = Path(sysconfig.get_path(name))
        if candidate not in package_paths:
            package_paths.append(candidate)
    # Include the actual package roots, including a supported user-site install.
    for name in ("PySide6", "shiboken6"):
        spec = importlib.util.find_spec(name)
        if spec is None or not spec.origin:
            raise ValueError(
                "PySide6-Essentials is required in this Python environment. "
                "Install tomc-memory[widget] before running the installer."
            )
        candidate = Path(spec.origin).resolve().parent.parent
        if candidate not in package_paths:
            package_paths.append(candidate)
    paths = [str(source), *(str(path) for path in package_paths)]
    checked_run(
        [
            sys.executable,
            "-I",
            "-B",
            "-c",
            f"import sys; sys.path[:0] = {paths!r}; "
            "import PySide6.QtCore, PySide6.QtGui, PySide6.QtWidgets; "
            "import tomc.usage_widget_qt",
        ]
    )
    return Runtime(
        executable=Path(sys.executable).absolute(),
        home=Path(sys.base_prefix),
        prefix=Path(sys.prefix),
        source=source,
        package_paths=tuple(package_paths),
        include=include,
        library=library,
        clang=clang,
        architecture=platform.machine(),
    )


def bootstrap(runtime: Runtime) -> str:
    paths = [str(runtime.source), *(str(path) for path in runtime.package_paths)]
    return (
        "import json, sys\n"
        f"sys.path[:0] = {paths!r}\n"
        f"sys.prefix = sys.exec_prefix = {str(runtime.prefix)!r}\n"
        f"if sys.argv[1:] == [{CHECK_ARGUMENT!r}]:\n"
        "    import PySide6.QtCore, PySide6.QtGui, PySide6.QtWidgets\n"
        "    import tomc.usage_widget_qt\n"
        "    print(json.dumps({'status': 'ok', 'python': sys.version.split()[0], "
        "'qt': PySide6.QtCore.qVersion(), 'source': tomc.usage_widget_qt.__file__}))\n"
        "else:\n"
        "    from tomc.usage_widget import main\n"
        "    main()\n"
    )


def c_string(value: str) -> str:
    """Fixed-width UTF-8 octal escapes safely represent every filesystem path."""
    return '"' + "".join(f"\\{byte:03o}" for byte in value.encode("utf-8")) + '"'


def launcher_source(runtime: Runtime) -> str:
    template = (ROOT / "scripts/macos_pet_launcher.c").read_text(encoding="utf-8")
    for key, value in {
        "PYTHON_HOME": str(runtime.home),
        "PYTHON_EXECUTABLE": str(runtime.executable),
        "BOOTSTRAP": bootstrap(runtime),
    }.items():
        template = template.replace(f"@{key}@", c_string(value))
    return template


def validate_destination(output: Path, replace: bool) -> bool:
    if output.suffix.lower() != ".app":
        raise ValueError("--output must name an .app bundle.")
    if output.is_symlink():
        raise ValueError("The output app must not be a symbolic link.")
    if not output.exists():
        return False
    info = output / "Contents/Info.plist"
    if not output.is_dir() or info.is_symlink() or not info.is_file():
        raise ValueError(f"Refusing to overwrite an unrelated item: {output}")
    try:
        existing = plistlib.loads(info.read_bytes())
    except (ValueError, plistlib.InvalidFileException) as exc:
        raise ValueError(f"Refusing to overwrite an unreadable app: {output}") from exc
    if not isinstance(existing, dict) or existing.get("CFBundleIdentifier") != BUNDLE_ID:
        raise ValueError(f"Refusing to overwrite an app with another bundle identifier: {output}")
    if not replace:
        raise ValueError(
            f"TOMC already exists at {output}. Quit it, then use --replace to update it; "
            "the previous app will be kept beside it as a timestamped backup."
        )
    return True


def build_bundle(app: Path, runtime: Runtime) -> dict:
    executable = app / "Contents/MacOS/TOMC"
    resources = app / "Contents/Resources"
    executable.parent.mkdir(parents=True)
    resources.mkdir()
    info = {
        "CFBundleIdentifier": BUNDLE_ID,
        "CFBundleName": "TOMC",
        "CFBundleDisplayName": "TOMC",
        "CFBundleExecutable": "TOMC",
        "CFBundlePackageType": "APPL",
        "CFBundleShortVersionString": "0.1.0",
        "CFBundleVersion": "1",
        "LSUIElement": True,
        "NSHighResolutionCapable": True,
        "NSPrincipalClass": "NSApplication",
    }
    (app / "Contents/Info.plist").write_bytes(plistlib.dumps(info))
    generated = app.parent / "launcher.c"
    generated.write_text(launcher_source(runtime), encoding="utf-8")
    checked_run(
        [
            runtime.clang,
            "-arch",
            runtime.architecture,
            "-I",
            str(runtime.include),
            str(generated),
            str(runtime.library),
            "-Wl,-rpath," + str(runtime.library.parent),
            "-framework",
            "CoreFoundation",
            "-o",
            str(executable),
        ]
    )
    executable.chmod(0o755)
    result = checked_run([str(executable), CHECK_ARGUMENT])
    try:
        check = json.loads(result.stdout)
    except ValueError as exc:
        raise ValueError("The compiled launcher returned an invalid runtime check.") from exc
    if check.get("status") != "ok":
        raise ValueError("The compiled launcher's runtime check did not pass.")
    dependencies = {
        "python": str(runtime.executable),
        "python_home": str(runtime.home),
        "environment": str(runtime.prefix),
        "source": str(runtime.source),
        "package_paths": [str(path) for path in runtime.package_paths],
        "python_library": str(runtime.library),
        "runtime_check": check,
    }
    (resources / "runtime.json").write_text(
        json.dumps(dependencies, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    (resources / "README.txt").write_text(
        "TOMC desktop companion for this Mac\n\n"
        "Double-click the app to start the normal companion. It waits for real TOMC "
        "events in the configured memory database; no demonstration data is created.\n"
        "This app does not enable login startup or change plugin/gateway settings.\n\n"
        "This is a local launcher, not a standalone distribution. Keep the source "
        "checkout, virtual environment and Python installation at the paths in "
        "runtime.json. Rebuild the app if any of these paths change. To use another "
        "computer, install its Python dependencies and run this installer there.\n\n"
        "To update: quit TOMC and rerun the installer with --replace and the same "
        "--output path. Only a matching TOMC bundle identifier is accepted; the old "
        "app is retained beside the new one as a timestamped backup.\n\n"
        "Installer command (add --output if using a custom destination):\n"
        + shlex.join(
            [str(runtime.executable), str(ROOT / "scripts/install_macos_pet.py"), "--replace"]
        )
        + "\n",
        encoding="utf-8",
    )
    return dependencies


def install(output: Path | str, *, replace: bool = False) -> dict:
    output = Path(output).expanduser().absolute()
    existed = validate_destination(output, replace)
    runtime = discover_runtime()
    output.parent.mkdir(parents=True, exist_ok=True)
    backup = None
    with tempfile.TemporaryDirectory(prefix=".tomc-app-build-", dir=output.parent) as work:
        staged = Path(work) / "TOMC.app"
        dependencies = build_bundle(staged, runtime)
        if validate_destination(output, replace) != existed:
            raise ValueError("The destination changed during the build; no app was replaced.")
        if existed:
            stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
            backup = output.with_name(f"{output.stem}.backup-{stamp}.app")
            os.rename(output, backup)
        try:
            os.rename(staged, output)
        except OSError:
            if backup is not None and not output.exists():
                os.rename(backup, output)
            raise
    return {"app": str(output), "backup": str(backup) if backup else None, **dependencies}


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=Path.home() / "Applications/TOMC.app")
    parser.add_argument(
        "--replace", action="store_true", help="Update a matching TOMC app and keep a backup."
    )
    args = parser.parse_args(argv)
    try:
        result = install(args.output, replace=args.replace)
    except (ValueError, OSError) as exc:
        print(f"TOMC installation failed: {exc}", file=sys.stderr)
        return 1
    print(f"Installed: {result['app']}")
    if result["backup"]:
        print(f"Previous app retained: {result['backup']}")
    print(f"Keep the Python environment at {result['environment']}")
    print(f"Keep the TOMC source at {result['source']}")
    print("Double-click TOMC.app to start it. Login startup and gateway settings are unchanged.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
