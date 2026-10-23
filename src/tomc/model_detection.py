"""Read model identifiers only; no credentials, prompts, screen or input control."""

import json
import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path

try:
    import tomllib
except ImportError:  # Python 3.10: only read top-level quoted model identifiers.
    tomllib = None


def detect(home=None, resumes=None):
    home = home or Path.home()
    result = {"checked_at": datetime.now(timezone.utc).isoformat(timespec="seconds"), "hosts": {}}
    hosts = result["hosts"]
    try:
        raw = (home / ".codex/config.toml").read_text("utf-8")
        config = tomllib.loads(raw) if tomllib else dict(re.findall(
            r'^\s*(model|model_provider)\s*=\s*"([^"\n]+)"', raw.split("\n[")[0], re.M))
        hosts["codex"] = {"model": config.get("model"), "provider": config.get("model_provider", "openai"),
                          "evidence": "Codex config.toml 的默认模型；可能被当前会话覆盖"}
    except (OSError, ValueError):
        hosts["codex"] = {"model": None, "evidence": "未读取到 Codex 默认模型"}
    if resumes is None:
        try:
            # Return only resume IDs, not process command lines or credentials.
            script = ("Get-CimInstance Win32_Process -Filter \"Name = 'claude.exe'\" | "
                      "ForEach-Object { if ($_.CommandLine -match '--resume[= ]([0-9a-f-]{36})') "
                      "{ $matches[1] } }")
            proc = subprocess.run(["powershell", "-NoProfile", "-NonInteractive", "-Command", script],
                                  capture_output=True, text=True, timeout=12,
                                  creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
            resumes = re.findall(r"[0-9a-f-]{36}", proc.stdout)
        except (OSError, subprocess.SubprocessError):
            resumes = []
    models = set()
    for resume in set(resumes):
        if not re.fullmatch(r"[0-9a-f-]{36}", resume):
            continue
        for transcript in (home / ".claude/projects").glob(f"*/{resume}.jsonl"):
            last = None
            try:
                with transcript.open(encoding="utf-8") as stream:
                    for line in stream:
                        try:
                            event = json.loads(line)
                            model = event.get("message", {}).get("model")
                            if event.get("type") == "assistant" and model and model != "<synthetic>":
                                last = model
                        except (ValueError, AttributeError):
                            continue
                if last:
                    models.add(last)
            except OSError:
                pass
    hosts["claude"] = {"model": next(iter(models)) if len(models) == 1 else None,
                       "provider": "anthropic",
                       "evidence": "运行中的 Claude Code 会话最近一条 assistant 的模型元数据；不代表下一次调用" if len(models) == 1
                       else "Claude Code 当前模型未确认（无活动记录或多个模型）"}
    hosts["cursor"] = {"model": None, "provider": "cursor",
                       "evidence": "未接入 Cursor 的逐请求模型记录；Auto 不猜测，需手选参考模型"}
    return result


def install_detection(directory=None):
    directory = directory or Path.home() / ".tomc"
    directory.mkdir(parents=True, exist_ok=True)
    found = detect()
    (directory / "detected_models.json").write_text(json.dumps(found, ensure_ascii=False, indent=2), "utf-8")
    path = directory / "pricing.json"
    try:
        settings = json.loads(path.read_text("utf-8"))
        if not isinstance(settings, dict):
            settings = {}
    except (OSError, ValueError):
        settings = {}
    # Preserve an explicit reference choice. Re-detect automatic selections on each install.
    if settings.get("selection") != "manual":
        host = settings.get("host", "claude")
        detected = found["hosts"].get(host, {})
        provider = detected.get("provider")
        settings = {"host": host, "provider": provider, "model": detected.get("model"),
                    "input_mode": "input", "variant": "standard-short" if provider == "openai" else "standard",
                    "selection": "detected-reference", "evidence": detected.get("evidence"),
                    "assumption": "未缓存、标准服务、基础上下文档位；未读取实际请求缓存/档位"}
        path.write_text(json.dumps(settings, ensure_ascii=False, indent=2), "utf-8")
    return found, settings
