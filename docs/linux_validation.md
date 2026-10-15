# Linux installation and feedback

**Installation succeeded on Ubuntu 24.04.5.** A fresh GitHub checkout ran the English web demo, and the downloaded Codex plugin installed and exposed all five tools. The Claude bundle's extracted MCP runtime also passed. This check used synthetic text and temporary settings, with no model calls.

The Codex ZIP needs UV and a Codex CLI with plugin commands; after those prerequisites, one installer handles registration. The source demo needs an environment and dependencies. The original system-Python setup failed on this machine because `ensurepip` was missing; the UV steps below worked. The README, quickstart and assistant guides now include that recovery path.

## What was tested

Verified on **2026-10-02**:

| Item | Tested configuration |
|---|---|
| Operating system | Ubuntu 24.04.5 LTS, x86_64 |
| Demo source | [`ac42b8464aed5346de8e8658d8bf778ee31c8b95`](https://github.com/ZipengWu365/TOMC/tree/ac42b8464aed5346de8e8658d8bf778ee31c8b95), freshly cloned |
| Python / Gradio | 3.12.13 / 5.49.1, installed with `.[demo]` |
| Downloaded plugins | [`v0.1.0-assistant-preview.2`](https://github.com/ZipengWu365/TOMC/releases/tag/v0.1.0-assistant-preview.2), tag commit `11071dae7bfb8fac488790bd0123ae823510718f` |
| Native Codex host | `codex-cli 0.159.0-alpha.12.1` |
| Environment manager | UV 0.11.20 |

| Check | Result |
|---|---|
| Fresh demo installation | Passed; `pip check` found no broken requirements |
| Documented combined installation | A second fresh environment installed `.[demo,mcp]`; imports, `pip check`, the offline example and default/custom-store Cursor link paths passed |
| Local startup | HTTP 200 at `http://127.0.0.1:7860` |
| Use now | Example preparation, exact clipboard copying, Chinese JSONL with Windows line endings and clearing stale results passed |
| Other views | Tour source inspection, updated state/snapshot, strategy comparison and research history selection passed |
| Browser layouts | 1440, 390 and 320 px; no page overflow, page errors or external browser requests |
| Offline Python API example | Passed without a reader request |
| Codex native installation | Fresh install, repeated install and reinstall after moving the directory passed; enabled skill recognized and five tools connected |
| Downloaded MCP runtimes | Both packages passed Unicode notes, restart recall, notebook isolation, temporary preparation and exact deletion; Codex also passed retry deduplication and missing-notebook checks |

The default API-migration example displayed **138 → 90** estimated message-content tokens, including task/system text, with a 64-token memory budget. Memory text alone was **93 → 45**. These lexical estimates exclude provider framing and are neither billed usage nor a general saving rate.

The browser and native CLI were exercised on Linux. Claude/Cursor GUI installation, automatic model tool selection, answer generation and permanent installation in a personal profile were not tested in this run. Earlier Windows model trials are recorded separately in [Validation](validation.md).

## Install the demo on Linux

Repository access is required while it is private. Install [UV](https://docs.astral.sh/uv/getting-started/installation/), then run:

```bash
git clone https://github.com/ZipengWu365/TOMC.git
cd TOMC
uv venv --python 3.12 --seed .venv
source .venv/bin/activate
python -m pip install -e '.[demo]'
python -m pip check
python -m demo.app
```

Open `http://127.0.0.1:7860`. Choose **Use now → Try demo**, inspect the prepared records and sources, then copy the prompt into a new chat. Dependency installation may need network access; default local preparation needs no API key or model download.

| Symptom | Recovery |
|---|---|
| `python: command not found` before activation | Use the UV commands above, or `python3 -m venv .venv`; activate the environment before using `python` |
| `ensurepip is not available` | For Ubuntu/Debian system Python, install its matching `python3-venv` package; the default distribution Python can use `sudo apt install python3-venv`. UV can manage Python separately |
| A failed command left a partial `.venv` | For this newly created environment, run `uv venv --python 3.12 --allow-existing --seed .venv`, activate it and reinstall the dependencies |
| Port 7860 is occupied | Run `PORT=7861 python -m demo.app` and open `http://127.0.0.1:7861` |
| Empty context at a small budget | Try **Balanced** or **More detail**; complete source lines or records must fit. Empty evidence is not useful compression |

The demo listens on loopback by default. Its printed URL is local to the machine running it; for an SSH session, forward port 7860 to your own computer. Stop the server with `Ctrl+C` when finished.

## Using the plugins

Follow the [assistant installation guide](assistant_plugin.md) for Claude, Cursor or Codex. Download preview.2 explicitly: it is a prerelease, so GitHub's stable “latest release” selector is not the right entry.

- **Codex:** extract the original ZIP to a lasting location and run `uv run --no-project install.py` there. Start a new Codex session and check for five TOMC tools. If `codex` is outside `PATH`, provide `--codex /absolute/path/to/codex`. Keep the extracted directory; rerun the installer after moving it.
- **Cursor or direct MCP:** install `.[mcp]` in your environment and generate configuration or the Cursor link from that environment. Regenerate it after moving the checkout or environment. A stdio server waiting silently in a terminal is normal; the client launches it itself.
- **Choose one TOMC registration per client:** native plugin or standalone MCP. Share the original ZIP/MCPB, rather than a generated configuration containing your machine's absolute paths.
- **Start with `prepare_context`:** pass a history, a specific next task and enough space for complete evidence. Inspect the returned state records and source text before using it. For API use, replace the original history with `prepared.messages`; for manual copying, use a new chat. Adding context to an existing long chat retains that chat's earlier messages.
- **Save only when needed:** notebooks are optional. Ask the assistant explicitly to remember a named notebook, then recall that name in another chat. Installing TOMC does not capture conversations automatically. Tool use also follows the assistant's permissions.
- **Share or separate notebooks deliberately:** clients using `~/.tomc/memory.sqlite3` under the same user account share notes. Across accounts, sharing requires access to the same actual database path. Use the native installer's `--store` option or the setup command's `--store` option for a separate database.

## Package verification and fixes

The actual GitHub downloads matched both their checksum sidecars and GitHub asset digests:

| Asset | Bytes | SHA-256 |
|---|---:|---|
| `tomc-memory-0.1.0.mcpb` | 84,418 | `83b1e3893d291e910f760d6f9ae091a692749e80a89bae8bb409d5e497b5528e` |
| `tomc-memory-codex-0.1.0.zip` | 89,242 | `36242fa2362d95c23fb55eb4ab6a6102845f77a3e6d6b503e514ce7112e6973e` |

The package runtime files also matched the tested main checkout. Both builders now pin ZIP creator metadata, removing a Windows/Linux hash difference. Rebuilt Linux packages are byte-identical to preview.2; no replacement downloads or runtime changes are needed. Regression tests simulate both host metadata defaults and compare complete archive bytes.

This revision updates installation guidance and packaging metadata. It leaves the compiler, frozen benchmark results and paper figures unchanged. All 128 repository tests, Ruff lint/format checks, strict documentation, wheel/source builds and frozen-result verification passed. A compact [verification receipt](linux_validation_20261002.json) records the environment, checks and artifact hashes without personal configuration or notebook contents.

## Actual Linux screenshots

The screenshots show the locally running English demo with the synthetic API-migration example after **Try demo**. They are separate from earlier Windows captures.

![Linux demo at desktop width](assets/linux_demo_desktop_20261002.png)

![Linux demo at mobile width](assets/linux_demo_mobile_20261002.png)
