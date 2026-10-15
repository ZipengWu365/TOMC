# Security and privacy

The compiler operates on text; it does not execute suggested verifier commands. The local Gradio app binds to localhost, disables analytics and sharing, and has no paid-reader action or credential form. On a Space, inputs are processed by that Space's server. The result JSON and evidence inspector contain original input excerpts; treat your own exports accordingly.

The optional Python reader obtains credentials only from environment variables, enforces HTTPS except for loopback, refuses redirects, limits response size, and sanitizes errors. It does not log prompts, response bodies or authorization headers. Suggested commands and ledger observations remain untrusted data.

The optional MCP integration runs over local stdio. It saves only content explicitly passed to its save tool in a named, local plaintext SQLite notebook; it has no arbitrary file-read, command execution, network reader or remote HTTP tool. Recalled text is returned to the client/assistant, which controls its subsequent processing. Names isolate notebooks in one database but are not an authentication boundary between clients sharing that file. Deletion is marked destructive and removes only the exact named notebook; it does not erase existing host chat messages or guarantee forensic erasure. New database files use owner-only permissions on systems honoring POSIX modes. The Gradio app does not expose this persistent store. Uploaded Gradio files use framework temporary storage with hourly cleanup of files older than one hour; avoid hosting that cache as public static content.

Run `make security-scan` to inspect release files and reachable Git blobs for credential patterns, excluded artifact names and large files. This targeted scan is a release check, not a guarantee that arbitrary user-supplied data is safe to publish. Follow the allowlist in [data and licensing](docs/data_and_license.md).

For a suspected secret exposure, revoke the credential at its provider and use a private reporting channel. Do not paste a working key into an issue. GitHub private vulnerability reporting may be enabled by the owner when public release is approved.
