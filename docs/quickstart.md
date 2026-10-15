# Quickstart

## Run the demo

Clone the repository, then install the demo with Python 3.10–3.13. CI covers Python 3.10 and 3.12.

```bash
git clone https://github.com/ZipengWu365/TOMC.git
cd TOMC
```

Create and activate an environment on Linux/macOS. The Linux-tested path uses [UV](https://docs.astral.sh/uv/getting-started/installation/) and includes pip:

```bash
uv venv --python 3.12 --seed .venv
source .venv/bin/activate
```

For system Python, use `python3 -m venv .venv` instead. Debian/Ubuntu need the matching `python3-venv` package; otherwise environment creation can fail with an `ensurepip` error. If a failed command left a partial environment, run `uv venv --python 3.12 --allow-existing --seed .venv`.

Or use Windows PowerShell with Python 3.12 installed:

```powershell
py -3.12 -m venv .venv
.venv\Scripts\Activate.ps1
```

Then install and launch:

```bash
python -m pip install -e '.[demo]'
python -m demo.app
```

Open [the local demo](http://127.0.0.1:7860). This installs from the checkout; there is no published PyPI package. Installation downloads dependencies, but default context preparation needs no model, API key or network request.

For the compiler alone, install with `python -m pip install -e .`. Core and MCP require Python 3.10+. Fresh Linux installation and interactive checks are recorded in [Linux validation](linux_validation.md).

## Prepare a prompt for your model

In **Use now**, click **Try demo** for a working example, or paste a history, describe the next task and click **Prepare**. Copy the prompt into a new chat, or send the prepared messages in place of the original history in your next API request. You can also load an example or upload a UTF-8 `.txt`, `.md`, `.json` or `.jsonl` file.

You do not need to choose a strategy. The convenience API keeps fitting histories intact. Longer histories use `tomc_raw` for supported task routes and wording-sensitive questions, or BM25 source retrieval otherwise. The budget covers memory text; task instructions and prompt framing add input afterward. Editing an input clears the old output.

From Python:

```python
from tomc import prepare_context

context = prepare_context(
    "preference = tea\npreference = decaf tea",
    "What is the current preference?",
    budget=128,
)
print(context.prompt)
# Or pass context.messages through your existing chat client.
```

The output can go to any text-based reader through your own client. The model and provider do not need to change. The bundled reader connector has a narrower scope: chat-completions-compatible HTTP APIs.

## Inspect what the reader receives

The **30-second tour** shows state changes and their supporting operations. **Workbench** lets you choose strategies and compare their memory outputs. Expand a source row to see its original text, message number and role.

The ledger includes candidate records that may not fit the budget. Only records marked `included` reach `compiled_memory`; the inspector itself is outside the memory budget. JSON exports include original evidence, so store runs containing your own data privately.

## Choose a strategy when needed

- `tomc_raw`, the compiler default, combines supported state, relation and count records with selected source text.
- `tomc` selects the records-only mechanism for inspection.
- `rag` retrieves source lines using BM25; `hybrid` chooses a route with fixed rules.
- `raw` retains the input without enforcing a memory cap.

Start with enough space for complete records, then lower the budget to inspect omissions. Ordinary prose is not automatically converted into correct state updates. See [method semantics](method.md) for supported syntax and routing limits.

```bash
tomc compile demo/examples/preferences.json --query "What are the current preferences?" \
  --strategy tomc_raw --budget 320 --output outputs/memory.json
```

For local persistence across chats, follow [assistant setup](assistant_setup.md). MCP saves text explicitly passed to its tools; it does not read your other conversations.
