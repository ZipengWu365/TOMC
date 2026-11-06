<div align="center">
  <img src="assets/tomc_logo_20261002.png" alt="TOMC Memory" width="320">
  <h1>TOMC Memory</h1>
  <p><strong>English</strong> | <a href="README_zh.md">简体中文</a> · v0.3.1 research preview · MIT · Python 3.10+</p>
</div>

I got tired of re-explaining my project to every new AI chat, and then getting the old version of a decision back.

**When a fact changes, only the latest version comes back.**

Say your project chat moved from Flask to Django, then FastAPI, then Litestar. TOMC Memory hands your assistant `framework = Litestar`, plus the line it came from.

**After installing, say to your assistant: "Try TOMC Memory".** In a terminal: `tomc try`.

- **Latest value, offline check (v0.3.0):** 144 questions per budget, each about a fact that changed 3 to 5 times. At the default budget the prepared context held the latest value every time (v0.2.1: 58%). At a 10% budget: 85% (v0.2.1: 51%). Synthetic notes and chats, no model call. We wrote these questions alongside the fixes, so treat them as our regression test, not an independent evaluation.
- **Smaller requests in Codex (0.1.0 preview, not re-run since):** 9 synthetic project chats of about 10K to 40K tokens, 5 questions each, `gpt-6.1-sol`. Keeping 40% of the history cut request input by 29.7% on average, and all 45 answers stayed right. One run per condition.
- **BEAM long-history benchmark (paper experiments):** same reader model on both sides, 3 readers, 6 other memory methods. TOMC had the higher mean score in 54 of 54 comparisons at 500K to 10M tokens, and 17 of 18 at 100K. Mean scores only; not comparable with other projects' BEAM numbers.

[Every number, with its conditions and failures](docs/evidence.md) · [Before you use it](#before-you-use-it) · [Install](#install)

<a id="before-you-use-it"></a>

## Before you use it

1. **It does not shrink the chat your assistant is already having.** Claude Code and Codex manage their own chat. TOMC Memory works on history you hand it and notes you saved. [Context ownership](docs/context_ownership.md)
2. **Short histories gain little.** Under about 10K tokens there is not much to cut. With the default budget, our earlier tests saved roughly 10–20% of input (Codex 9.2%, Claude API-style 19.8%; 0.1.0 previews). Smaller budgets save more but can drop the latest value. Check them on your own tasks first. The default keeps 80% of a history up to 10K tokens, sliding to 60% at 1M, and never less than 1,024 tokens.
3. **It matches words, not meaning.** A reworded update such as "scratch that, go with Django" can be missed, mostly at small budgets. When a later line may have changed a value, the value is marked `STATE?` and that line is attached so you or your assistant can check it.
4. **What gets stored, and how to erase it.** Results of `prepare_context` and `recall_memory` are not saved unless you turn it on (`tomc settings --save-mcp-results on`). Notes you save with `remember_memory` stay on your computer in `~/.tomc/memory.sqlite3`. Delete one notebook with `forget_memory`, or everything with `tomc erase-all --yes`. [Security and privacy](SECURITY.md)
5. **Not every client is checked.** Codex and Claude Code passed real model calls with earlier previews. For Cursor, TRAE and WorkBuddy the setup is written, but their tool calls have not been checked on real machines. Claude Desktop installation has not been checked in the app.
6. **The paper is not public yet.** The benchmark numbers come from our own runs and setup. The [evidence page](docs/evidence.md) lists sources, sample sizes and what can be rechecked offline (`make reproduce`).

<a id="install"></a>

## Install

Each path ends the same way: say **"Try TOMC Memory"** in a new chat, and run `tomc doctor` if something looks wrong. The Claude Code and Codex plugins need [uv](https://docs.astral.sh/uv/getting-started/installation/). Running from source needs Python 3.10 or newer (`python3 --version`; the macOS system Python 3.9 is too old).

<a id="claude-code"></a>

### Claude Code

```text
/plugin marketplace add ZipengWu365/TOMC
/plugin install tomc-memory@tomc
```

Start a new session, check `/mcp` for `plugin:tomc-memory:tomc`, then say "Try TOMC Memory" or run `/tomc-memory:try`. [More Claude Code notes](docs/assistant_plugin.md#claude-code)

<a id="codex"></a>

### Codex

Download [tomc-memory-codex-0.3.1.zip](https://github.com/ZipengWu365/TOMC/releases/download/v0.3.1-preview.1/tomc-memory-codex-0.3.1.zip), unzip it into a folder you will keep, and run there:

```bash
uv run --no-project --python 3.12 install.py --check
uv run --no-project --python 3.12 install.py
```

The installer starts the server once to check it. Open a new Codex session and say "Try TOMC Memory". [Full Codex steps](docs/assistant_plugin.md#codex)

<a id="any-mcp-client"></a>

### Any MCP client (Cursor, Claude Desktop, WorkBuddy, TRAE …)

```bash
git clone https://github.com/ZipengWu365/TOMC.git && cd TOMC
python3 -m venv .venv && .venv/bin/python -m pip install -e '.[mcp]'
.venv/bin/tomc setup --client cursor --write   # or claude-desktop, claude-code, codex, workbuddy
.venv/bin/tomc doctor
```

`--write` backs up the client's config file first and keeps your other servers. For TRAE or a project file, add `--config path/to/mcp.json`. Restart the client and say "Try TOMC Memory". On Windows use `py -3.12 -m venv .venv` and `.venv\Scripts\`. [Per-client guides](docs/assistant_plugin.md#setup-write)

<a id="python-api"></a>

### Python API

```python
from tomc import prepare_context  # pip install -e . from a clone; no dependencies

prepared = prepare_context(history, task)
response = client.chat.completions.create(model=model, messages=prepared.messages)
```

Send `prepared.messages` in place of the old history; appending it adds input. `.venv/bin/tomc try` shows a worked example offline. [API guide](docs/api_reference.md)

<a id="mainland-china-network"></a>

### Mainland China network

If GitHub or PyPI downloads stall, use a mirror for pip and uv:

```bash
python3 -m pip install --user uv -i https://pypi.tuna.tsinghua.edu.cn/simple
export UV_DEFAULT_INDEX=https://pypi.tuna.tsinghua.edu.cn/simple
export UV_PYTHON_INSTALL_MIRROR=https://registry.npmmirror.com/-/binary/python-build-standalone
python3 -m uv run --no-project --python 3.12 install.py   # Codex installer, run in the unzipped folder
```

For a source install, add `-i https://pypi.tuna.tsinghua.edu.cn/simple` to the `pip install` line. In PowerShell, set the variables with `$env:UV_DEFAULT_INDEX="…"`.

## Go deeper

- [Evidence and claims ledger](docs/evidence.md): every number, its source file, model, sample size and version, plus the negative results.
- [What changed in 0.3.1](docs/release_notes_0.3.1.md) · [in 0.3.0](docs/release_notes_0.3.0.md) · [Reproduce the offline checks](docs/reproducibility.md) · [Independent replications](REPLICATIONS.md)
- [Switch assistants and keep your notes](docs/usage_tips.md#reuse-notebooks): save in Codex, continue in Claude Code, on one computer.
- [Desktop companion (beta)](docs/desktop_companion.md): a small cat that shows today's estimated context reduction and makes a [weekly report card](docs/share_card.md) you can share; Windows and macOS. The optional request gateway is Windows only. Linux has the plugins and MCP server only.
- [Local demo](docs/quickstart.md) · [How it works](docs/method.md) · [Automatic API request loop](docs/context_ownership.md) · [Usage tips](docs/usage_tips.md) · [Validation record](docs/validation.md)
- [Video overview (1:37)](launch/media/v13/videos/TOMC_Overview_EN.mp4). One Codex number in the video has no protocol in this repository; see [media notes](launch/media/v13/README.md).

## Community, citation and license

<!-- community-entry:start -->
**Try, compare, contribute:** [First-run reports](https://github.com/ZipengWu365/TOMC/issues/11) · [Context-compression evaluation note](https://github.com/ZipengWu365/ZipengWu365/blob/main/notes/2026-10-27-context-compression-checklist.md) · [Contribution guide](CONTRIBUTING.md)

Follow [Zipeng Wu](https://github.com/ZipengWu365) for work across time-series research software and AI task memory. Star this repository to save TOMC; use Watch settings for project notifications. Following or starring is optional and is never required for help.
<!-- community-entry:end -->

<p><a href="https://github.com/ZipengWu365/TOMC/stargazers"><img src="assets/traffic/stars.svg" alt="GitHub Stars" height="20"></a> <a href="docs/traffic_metrics.md"><img src="assets/traffic/clones-total.svg" alt="Cumulative recorded clones" height="20"></a></p>
<!-- traffic-status:start -->
  <p>Cumulative clones · recorded since 2026-10-02 · updated 2026-11-06 UTC. <a href="docs/traffic_metrics.md">Method and updates</a></p>
<!-- traffic-status:end -->

MIT License: free to use, change and ship, including commercially; keep the copyright and license notice. If TOMC Memory helps your research, please cite it with [CITATION.cff](CITATION.cff) (GitHub's "Cite this repository" button). Examples are synthetic; the repository holds numeric benchmark aggregates only, without question text, answers or API payloads. [Data provenance](DATA_PROVENANCE.md) · [Data and licensing](docs/data_and_license.md)
