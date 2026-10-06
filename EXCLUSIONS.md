# Release exclusions

Only selected author-owned kernels, new packaging/UI/tests/docs, original synthetic scenarios, and numeric aggregate statistics are included.

Excluded: provider credentials and real environment files; private provider endpoints; raw reader/judge requests and responses; job grids containing prompts or labels; benchmark source text; original conversation or record IDs; third-party repository mirrors; model weights and caches; virtual environments; mathematical experiments; invalid RULER/SWE adaptations; incomplete/debug/aborted runs; unsafe and interim staging packages; private evidence archives and paper Git history.

The private evidence dataset and manuscript repository are not mirrored into this project. Hashes identify the local source artifacts without exposing their text. The release manifest excludes only itself and its companion SHA256SUMS, as well as ignored local build/runtime files. Public GitHub/HF visibility and PyPI publication are not authorized by this staging release.

User MCP notebooks (`.tomc/`, `*.sqlite3`, SQLite journal/sidecar files), uploaded personal histories and generated personal handoffs are runtime data, not release assets. The default notebook lives outside the checkout under the user's home directory. Only synthetic notebook tests belong in this repository.
