# Security and privacy

## Summary

TOMC Memory runs on your computer and uploads nothing to the TOMC Memory project: there is no
telemetry, no account and no TOMC Memory server. Everything it keeps is in one local SQLite file,
`~/.tomc/memory.sqlite3` (or the path in `TOMC_MEMORY_PATH`), plus a few small settings files
next to it. The optional request gateway is the most trusted part. When you turn it on, every
Codex or Claude Code model request, including your sign-in token or API key, passes through it
on `127.0.0.1` on its way to OpenAI or Anthropic. The gateway forwards credentials in memory and
never writes them to disk. It writes request metadata (IDs, model names, token counts, times).
While **Save context records** is on, it also keeps the compressed old conversation and your
latest message, with common secrets removed first, for 30 days. Turn that switch off and no
conversation text from the gateway reaches the disk.

## Components and trust boundaries

| Component | How it runs | What it can reach |
|---|---|---|
| MCP server (`tomc mcp`, the Claude Code / Codex / Claude Desktop plugins) | A child process of the host, over stdio only. No listening socket. Exits when the host closes stdin or when its parent process exits (checked every 2 seconds). | Only the arguments the host passes to its tools, and the local database. No file reading, command execution or network tools. |
| Request gateway (`tomc.request_gateway`) | A per-user background process listening on `127.0.0.1:43187` (IPv4 loopback only). | Full request bodies and request headers, including credentials, for Codex (`/codex` → `https://chatgpt.com/backend-api/codex`) and Claude Code (`/claude` → `https://api.anthropic.com`). Model responses stream through it. |
| Desktop companion (the cat) | A Qt app started by you or at sign-in. | Reads the local database. Reads the model name from Claude Code transcripts and Codex thread names (it does not copy their text). Starts the official `codex app-server` once a minute to read your remaining Codex allowance; Codex itself makes that request. |
| Installers (`scripts/install_*.py`, `plugins/codex/install.py`) | Run by you. Preview is the default; nothing changes without `--install` / `--activate`. | Files in your home folder listed under [What the installers change](#what-the-installers-change). No administrator rights. |

The gateway trusts any process on this computer that can connect to `127.0.0.1:43187` (see
[Local attack surface](#local-attack-surface)). Text returned by `prepare_context`,
`recall_memory`, `get_context` and `make_handoff` goes back to the host model, which decides what
to do with it; treat it as untrusted evidence.

## What is seen, what is stored

All stored items live in `~/.tomc/memory.sqlite3` unless noted. "Erase all" means the
`erase_all_memory` MCP tool, `tomc erase-all --yes`, or **Erase all records…** in the
companion's context window.

| Data | Seen by | Stored? | Where / retention | Switch |
|---|---|---|---|---|
| ChatGPT sign-in token, Anthropic API key or OAuth token, account-ID headers | Gateway (in memory, forwarded upstream) | **Never** | — | — |
| Full request bodies, model answers | Gateway | **Never** (answers are only scanned for token-usage numbers) | — | — |
| Compressed old conversation (may include tool output, file excerpts and pasted secrets) and your latest message, from gateway requests | Gateway | Yes, **only while Save context records is on** (on by default). Common secrets are replaced with `[REDACTED]` first. | Context snapshots table; deleted after **30 days** (`tomc settings --retention-days N`), on erase all, or one at a time in the companion | **Save context records** (`tomc settings --save-contexts on/off`) |
| Claude Code replay data (the compressed prefix TOMC Memory sent, so later requests in the same turn see identical input) and the latest message | Gateway | Recording on: a redacted copy on disk. Recording off: **in the gateway's memory only**, lost when it stops. | Replay table; deleted after 30 days, when Claude Code compacts the chat, on erase all | Same switch |
| `prepare_context` / `recall_memory` results and their task | MCP server | **No, by default.** Only if you turn on saving MCP results (and Save context records is on). Redacted first. | Context snapshots table, 30 days | `tomc settings --save-mcp-results on` (default off) |
| Notebook text you save with `remember_memory` | MCP server | Yes, exactly as given (not redacted: you chose to save it) | Notebooks table, until `forget_memory` or erase all | Only the explicit tool call |
| Imported context bundles | Companion | Yes, as imported | Kept until you delete them or erase all (no time limit) | Your import action |
| Request metadata: request ID, host, session ID, model name, request state and reason codes, token counts, timestamps | Gateway | Yes, for every gateway request, including pass-through and paused requests | Request activity table; no time limit; cleared by erase all | None |
| Session metadata: host, session ID, conversation title and project folder (from the optional session hooks), on/off choice | Hooks, gateway | Yes | Sessions table; erase all removes them, but keeps the off switch (without title and folder) for paused sessions | None |
| Numeric statistics (daily token totals, per-request counts) | MCP server, gateway | Yes, numbers and random IDs only | Usage tables; kept by erase all so the companion's history stays | None |
| MCP preparation receipts: host, session ID, token counts, time | MCP server | Yes | Receipts table; no time limit; cleared by erase all | None |
| Your switches, UI language, which notices you have seen | Companion, CLI | Yes | `memory.sqlite3`, `~/.tomc/ui_settings.json`, `~/.tomc/privacy-notice-v1`, `~/.tomc/animation_receipts.jsonl` (IDs and counts only) | — |
| Installer backups of `~/.codex/config.toml` and `~/.claude/settings.json` (these can contain tokens in an `env` section) | Installers | Yes, owner-only (`0600`) | `~/.codex/tomc/archive/`; never deleted automatically | — |

Redaction is a fast pattern pass, not a guarantee. It recognises common API key and token
shapes (`sk-…`, `sk_live_…`, `ghp_…`, `github_pat_…`, `hf_…`, `AKIA…`, Slack and Google keys,
JWTs), `Bearer`/`Basic` credentials, PEM private key blocks, credentials in URLs, and
`KEY=value` / `"api_key": "…"` assignments whose name contains words such as key, secret,
token, password or credential. A secret in any other shape is stored as written. Snapshots saved
by TOMC Memory 0.2.x are redacted once, the first time the new gateway or MCP server starts.

New database files are created owner-only (`0600`, folder `0700`) on systems with POSIX
permissions, whichever component creates them; the gateway and MCP server also tighten an
existing database that was readable by others. SQLite `secure_delete` is on for every write,
so deleted text is overwritten, and the file is rebuilt with `VACUUM` after forget, erase all and
the start-up clean-up. The database is not encrypted; anyone who can read files as
your user (or an administrator, or your backup and sync tools) can read it.

## Credentials

The gateway reads `Authorization`, `x-api-key` and the account headers only to copy them onto
the upstream request. It never logs URLs, headers or bodies (the standard access log and
traceback printing are disabled), and never stores them. The client keeps its own sign-in; the
gateway changes no authentication setting. Tests that check this:

- `tests/test_request_gateway.py::test_http_and_sse_compress_preserve_auth_headers_and_record_actual_usage`
  sends fake credentials through the gateway for both hosts and checks they reach the upstream
  and are absent from the database file.
- `tests/test_request_gateway.py::test_recording_off_writes_no_conversation_text_to_disk` and
  `::test_recorded_contexts_and_replay_data_are_redacted_on_disk` check the database bytes for a
  fake key and a sentence from the conversation.
- `tests/test_privacy.py` covers redaction, retention, forget and erase all, and file permissions.

## Local attack surface

These limits remain in this version:

- **No client authentication.** Any program running on this computer can send requests through
  the gateway, and the gateway will forward them and record their metadata (and, with recording
  on, their compressed history) under whatever session ID they claim. A program that can do this
  can usually read your files anyway, but it can also plant a fake snapshot that a later
  `make_handoff` would offer to another assistant.
- **Port squatting.** The address is fixed (`127.0.0.1:43187`). If TOMC Memory is not running,
  another local program could listen there and receive the requests, tokens and prompts your
  clients send to it. The gateway's socket uses `SO_REUSEADDR`, which on Windows may let another
  program bind the same port even while the gateway runs. Run [Restore direct connection](#failure-and-recovery) whenever
  you stop using the gateway.
- **Shared computers.** On a computer where other people have accounts, loopback is shared
  between users: another user's program can reach your gateway and could squat your port. Use
  the gateway only on a computer you do not share.
- **All MCP clients share one database.** Notebook names separate notebooks but are not a
  security boundary. Any MCP client you connect (Cursor, Claude Desktop, …) can list and read
  saved snapshots, including those the gateway recorded from Codex or Claude Code.

The gateway refuses requests that carry a browser `Origin` header, requests whose `Host` is not
`127.0.0.1` or `localhost` (DNS rebinding), and paths with `..` or backslashes. It only binds
IPv4 loopback, requires HTTPS for remote upstreams, rejects credentials in upstream URLs, never
follows redirects, limits decoded request size to 64 MiB and does not retry model requests.
Outgoing requests honour the standard `HTTPS_PROXY` / `HTTP_PROXY` variables.

## Network connections

TOMC Memory itself makes these connections, and no others:

| When | Destination | What is sent |
|---|---|---|
| Gateway on, every model request | `chatgpt.com` (Codex) and `api.anthropic.com` (Claude Code) | The client's own request, with old history compressed. This replaces the direct connection the client would otherwise make. |
| `scripts/install_current_pet.py` (installing the companion on macOS or from a checkout) | Four public pricing pages: `developers.openai.com`, `platform.claude.com`, `api-docs.deepseek.com`, `cursor.com` | A plain GET with `User-Agent: TOMC-price-sync/1.0`; nothing about you. |
| Companion → **Feedback** in the savings analysis, after you tick the confirmation | Opens a `github.com` new-file page in your browser, prefilled with the report | The report shown in the dialog (TOMC Memory version, operating system, period, token totals, work categories, your optional comment) travels to GitHub inside the page link. Nothing is published until you confirm on GitHub, which then creates a public pull request. |
| First start of the Claude Code / Codex / Claude Desktop plugin (`uv run --locked`) and the installers (`pip install`) | PyPI, through `uv` or `pip` | Normal package downloads. |
| Companion health check | `127.0.0.1` only | — |

The companion also starts `codex app-server` (see above); that is Codex talking to OpenAI with
your Codex sign-in. The MCP server makes no network connections.

## Deletion, retention and uninstall

- **Forget one notebook:** `forget_memory` deletes the notebook and every saved context prepared
  from it.
- **Delete one context:** in the companion's context window.
- **Erase all:** `erase_all_memory` (MCP tool; marked destructive and requires
  `confirm="ERASE ALL"`), `tomc erase-all --yes`, or **Erase all records…** in the companion.
  It deletes notebooks, saved contexts, Claude replay data, request and session metadata and
  preparation receipts, then rebuilds the file. It keeps your switches, paused-session switches
  and numeric statistics. A running gateway notices the erase and drops the replay data it holds
  in memory.
- **Retention:** saved contexts and Claude replay data older than 30 days are deleted when the
  gateway or the MCP server starts and whenever a new context is saved. Change it with
  `tomc settings --retention-days N` (1–3650). Notebooks, imported bundles and request metadata
  have no time limit.
- **Uninstall** (`install_windows_companion.py --uninstall RECEIPT`, or
  `install_request_gateway.py --restore RECEIPT`) restores host settings and removes what the
  installer added. It never deletes `~/.tomc` or the backup archive; use erase all first, then
  delete `~/.tomc` and `~/.codex/tomc/archive` yourself if you want nothing left.

## Failure and recovery

If the gateway is not running (sign-in startup disabled, process killed, Python upgraded),
Codex and Claude Code still point at `127.0.0.1:43187` and their requests fail with a
connection error. Restore the direct connection; this works with TOMC Memory stopped:

- `python -m tomc restore-direct`, or run the file `src/tomc/direct_connection.py` with any
  Python 3.10+ (it needs only the standard library);
- on Windows, Start menu → **TOMC Memory - Restore direct connection**, or
  `python scripts/install_windows_companion.py --restore-direct`;
- or `python scripts/install_request_gateway.py --restore-direct`.

It removes only `openai_base_url` from the top level of `~/.codex/config.toml` and
`ANTHROPIC_BASE_URL` (with `CLAUDE_CODE_GATEWAY_HINT_HEADERS`) from the `env` section of
`~/.claude/settings.json`, and only when they still point at the local gateway. Everything else
in those files stays, including changes Codex or Claude Code made after installation. Running it
again reports `already_restored`. Then quit and reopen Codex and Claude Code. To do it by hand,
delete those two entries.

Receipt-based restore (`--restore RECEIPT`) returns a file to its exact backup when nobody has
changed it since installation; once the host has edited it, only TOMC Memory's keys are removed.
Other files changed since installation are left alone and listed. It is safe to run twice.

## What the installers change

- **Gateway activation** (`install_request_gateway.py --activate`, also run by the Windows
  installer with `--gateway`): sets `openai_base_url` in `~/.codex/config.toml`; sets
  `env.ANTHROPIC_BASE_URL` and `env.CLAUDE_CODE_GATEWAY_HINT_HEADERS` in
  `~/.claude/settings.json`; writes `~/.codex/tomc/gateway-routing.json`; updates the
  companion's modules in `~/.codex/tomc/pet-current` if present. It refuses to replace an
  existing custom endpoint, provider or active Codex profile. Every changed file is backed up
  byte for byte, owner-only, with a receipt under `~/.codex/tomc/archive/`.
- **Windows companion** (`install_windows_companion.py --install`): creates a virtual
  environment `~/.codex/tomc/hourglass-ui` and installs `PySide6-Essentials>=6.8,<7` into it;
  copies the TOMC Memory source to `~/.codex/tomc/pet-current`; adds `TOMC.lnk` to the Start
  menu and `TOMC Cat.lnk` to your Startup folder. With `--gateway` it also stages a gateway
  runtime `~/.codex/tomc/gateway-<version>-<time>` with its own environment
  (`requirements-gateway.txt`), adds `TOMC Gateway.lnk` to Startup and the restore shortcut to
  the Start menu. It runs PowerShell with `-ExecutionPolicy Bypass` to create shortcuts and to
  find its own processes; some security tools flag that pattern. Replaced files are archived and
  restored by `--uninstall`.
- **macOS app** (`install_macos_pet.py`): builds `TOMC.app`; does not set up login startup or
  change host settings.
- **Session hooks** (`install_session_hooks.py`): adds metadata-only hooks to Codex and Claude
  Code settings, preserving the rest; preview first.

## Supply chain and verifying a release

- The core compiler has no third-party dependencies. The gateway pins `httpx`, `zstandard` and
  `tomlkit` to exact versions, but without hashes, and their own dependencies are not pinned.
  The Windows companion installs PySide6 within a version range with `pip --upgrade`. The
  plugins use `uv run --locked` against the committed `uv.lock`.
- Installed runtimes live in folders your user can write to, so any program running as you can
  change them.
- `SHA256SUMS` lists the SHA-256 of every file in a release (regenerated with `make manifest`).
  Check a download with `sha256sum -c SHA256SUMS` (macOS: `shasum -a 256 -c SHA256SUMS`;
  Windows: `Get-FileHash`). Plugin archives in `plugins/downloads/` have their own `.sha256`
  files. These hashes are published in the same repository and are not signed, so they detect
  corruption, not a compromised repository. Compare them with the tagged GitHub release when in
  doubt.
- `make security-scan` checks release files and Git history for credential patterns and
  excluded artifacts. It is a release check, not a guarantee.

## Known limits

- **Old tool output becomes part of a user message.** To shorten a request, the gateway
  replaces old turns, including old tool results such as web pages and files the assistant
  read, with one compressed block inside a message with the `user` role, wrapped in
  `<tomc_history>` and labelled as untrusted evidence. A prompt injection hidden in that old
  output therefore reaches the model from a user-role message rather than from a tool result,
  which models usually trust more. Only the label pushes back against it. Moving this evidence
  out of the user role is not part of this release.
- With recording off, Claude Code replay data lives only in the gateway's memory. If the
  gateway restarts in the middle of a turn, that turn's next request goes through unchanged.
  After a restart with recording on, replay uses the redacted copy; if redaction changed
  anything, the replayed text differs slightly from what the model saw before.
- Compressed context may omit details. Reported savings are estimates, not billing.
- The Gradio demo runs on your computer. No hosted demo is deployed (the earlier one was removed on
  2026-10-10). If you deploy one, for example to a Hugging Face Space, text pasted into it is
  processed on that server.

## Reporting a vulnerability

Please report privately through GitHub: on the repository's **Security** tab choose **Report a
vulnerability**. If that option is not available, open an issue asking for a private contact,
without details. Do not paste a working key into an issue; if a secret was exposed, revoke it at
its provider first.
