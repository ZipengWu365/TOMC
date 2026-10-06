"""The first-use path: paste, describe the next task, copy into any model."""

from __future__ import annotations

import json
from importlib.resources import files

import gradio as gr

from tomc import compile_memory, prepare_context
from tomc.input import parse_history
from tomc.tokenization import get_counter

SIZES = {"Small request": 64, "Balanced": 1024, "Compact": 512, "More detail": 4096}

API_EXAMPLE = "Continue an API migration"
API_HISTORY = (
    "framework = Flask\n"
    "backup_framework copies framework\n"
    "framework = FastAPI\n"
    "Monday notes: the team reviewed the project backlog, discussed deployment windows and agreed "
    "to keep the public API routes and response fields unchanged during the refactor.\n"
    "Tuesday notes: the migration plan still needs a review from the database owner, and the "
    "pagination tests have not yet been written or run.\n"
    "Wednesday notes: the team checked the release checklist, added a rollback task, and postponed "
    "the documentation update until after the test results are available."
)
API_TASK = "What are the current framework and backup_framework values?"


def quick_example(name: str) -> tuple[str, str]:
    """Load original examples as plain text, without requiring JSON knowledge."""
    if name.split(" / ", 1)[0] == API_EXAMPLE:
        return API_HISTORY, API_TASK
    if name.split(" / ", 1)[0] == "Track changing preferences":
        data = json.loads(
            files("tomc").joinpath("data/preferences.json").read_text(encoding="utf-8")
        )
        return "\n\n".join(m["content"] for m in data["messages"]), data["query"]
    return (
        "Monday: The workshop is planned for 20 people.\n"
        "Tuesday: Attendance increased to 28. Two attendees need step-free access.\n"
        "Wednesday: Venue A has stairs. Venue B has a lift and holds 35 people.\n"
        "Venue B is available Friday afternoon. The room has not been booked yet.",
        "Which venue fits, and what still needs to be done?",
    )


def message_content_counts(
    before: list[dict[str, str]], after: list[dict[str, str]]
) -> tuple[int, int]:
    """Count all message text with one estimator, excluding provider framing."""
    counter = get_counter("regex")
    return tuple(sum(counter.count(m["content"]) for m in messages) for messages in (before, after))


def input_reduction(before: int, after: int) -> str:
    """Display signed savings, including pass-through and increased input."""
    saved = before - after
    amount = f"{saved:+,}" if saved else "0"
    percent = f"{100 * saved / before:+.1f}%" if before else "not defined"
    if not saved and before:
        percent = "0.0%"
    qualifier = " Input increased." if saved < 0 else ""
    return f"**Estimated input reduction:** {amount} tokens ({percent}).{qualifier}"


def prepare_view(history: str, task: str, size: str) -> tuple:
    """Return the actual prompt with compact status and optional evidence."""
    try:
        prepared = prepare_context(history, task, SIZES[size.split(" / ", 1)[0]])
    except (ValueError, TypeError, KeyError) as exc:
        hints = {
            "Describe what you want the model to do next.": "Add your next task, for example: Which venue fits, and what still needs to be done?",
            "Paste a history or load an example first.": "Paste your history or click Try demo to prepare a sample.",
            "Use at most 200,000 characters per history.": "Shorten the history or split it into smaller batches of up to 200,000 characters.",
        }
        message = str(exc)
        raise gr.Error(
            hints.get(message, f"{message} Check your input; JSON and JSONL need text messages.")
        ) from None
    result = prepared.compilation
    stats = result.stats
    note = prepared.note
    if not prepared.prompt:
        note = (
            "This budget cannot fit a complete source line or record. Break long paragraphs "
            "into shorter lines, or choose a larger memory size. If More detail is already "
            "selected, add line breaks between sentences."
        )
    raw = compile_memory(parse_history(history), task.strip(), stats.token_budget, "raw")
    request_before, request_after = message_content_counts(
        raw.reader_messages(task.strip()), prepared.messages
    )
    reduction = (
        input_reduction(request_before, request_after)
        if prepared.prompt
        else "**Unusable request:** no evidence fits. Increase the memory size before sending it."
    )
    status = (
        f"**{'Ready to copy' if prepared.prompt else 'No complete record fits'}** · "
        f"**API message-content estimate:** {request_before:,} → {request_after:,} tokens\n\n"
        f"{reduction}\n\n"
        f"**Memory only:** {stats.input_tokens:,} → {stats.output_tokens:,} tokens "
        f"(budget {stats.token_budget:,}). {note}\n\n"
        "The estimate includes the same system instructions and task on both sides. It excludes "
        "provider framing, tool schemas and hidden tokens; this is not measured API usage or a bill."
    )
    explanation = (
        f"**Selected method:** `{result.diagnostics['selected_strategy']}`. "
        f"{result.diagnostics['route_reason']}\n\n"
        "Histories that fit are kept whole. For longer input, fixed rules select a method; "
        "ordinary prose uses retrieval of original text. Your model answers after you pass it this context.\n\n"
        "For the next API request, use these prepared messages in place of the original history. "
        "Appending this result to an existing long chat does not remove that chat's history."
    )
    return prepared.prompt, status, explanation, result.to_dict(), prepared.messages


def prepare_submission(history: str, task: str, size: str) -> tuple:
    """Keep the submitted inputs beside a result until the browser checks freshness."""
    prompt, status, explanation, audit, messages = prepare_view(history, task, size)
    return (
        prompt,
        status,
        explanation,
        {**audit, "_submitted_inputs": [history, task, size]},
        messages,
    )


_CLEAR_JS = """() => ["", "Inputs changed. Prepare again.", "", {}, []]"""
_PUBLISH_JS = r"""(prompt, status, explanation, audit, messages) => {
    const submitted = audit?._submitted_inputs;
    const history = document.querySelector('#easy-history textarea')?.value;
    const task = document.querySelector('#easy-task textarea')?.value;
    const size = document.querySelector('#easy-size input:checked')?.value;
    const normalize = value => value?.replace(/\r\n?/g, "\n");
    if (!submitted || normalize(submitted[0]) !== normalize(history) || normalize(submitted[1]) !== normalize(task) || submitted[2] !== size) {
        return Array.from({length: 5}, () => ({__type__: "update"}));
    }
    const cleanAudit = {...audit};
    delete cleanAudit._submitted_inputs;
    return [prompt, status, explanation, cleanAudit, messages];
}"""


def upload_text(data: bytes | None) -> str:
    """Decode an uploaded file without accepting arbitrary server-side paths."""
    if data is None:
        return ""
    if len(data) > 800_000:
        raise gr.Error("Use a text file up to 800 KB. Shorten it or split it into smaller files.")
    try:
        text = data.decode("utf-8-sig")
    except UnicodeDecodeError:
        raise gr.Error("Save the file as UTF-8 text, then upload it again.") from None
    if len(text) > 200_000:
        raise gr.Error("Use at most 200,000 characters. Shorten the file or split it into batches.")
    return text


def build_easy() -> None:
    """Expose two inputs and one main action; keep compiler settings out of the way."""
    gr.Markdown("**Prepare a smaller API input.** No model call here.")
    with gr.Row(equal_height=False):
        with gr.Column(scale=1, min_width=260):
            history = gr.Textbox(
                label="1. History",
                placeholder="Paste a conversation history or notes.",
                lines=4,
                max_lines=12,
                elem_id="easy-history",
            )
            task = gr.Textbox(
                label="2. Next task",
                placeholder="For example: Which venue fits, and what still needs to be done?",
                lines=2,
                elem_id="easy-task",
            )
            with gr.Row():
                run = gr.Button("Prepare", variant="primary", elem_id="easy-run", scale=3)
                try_example = gr.Button("Try demo", elem_id="easy-try", scale=1, min_width=120)
            with gr.Accordion("Upload or try an example", open=False):
                upload = gr.File(
                    label="UTF-8 text, Markdown, JSON or JSONL",
                    file_types=[".txt", ".md", ".json", ".jsonl"],
                    type="binary",
                    elem_id="easy-upload",
                )
                example = gr.Dropdown(
                    [API_EXAMPLE, "Plan a workshop", "Track changing preferences"],
                    label="Choose an example",
                    value=API_EXAMPLE,
                )
                load = gr.Button("Load example")
            with gr.Accordion("Memory size", open=False):
                size = gr.Radio(
                    list(SIZES),
                    value=next(iter(SIZES)),
                    label="How much context to keep",
                    elem_id="easy-size",
                )
        with gr.Column(scale=1, min_width=260):
            status = gr.Markdown(
                "Your ready-to-use context appears here.",
                elem_id="easy-status",
            )
            prompt = gr.Textbox(
                label="3. Copy this into your model",
                lines=10,
                max_lines=20,
                interactive=False,
                show_copy_button=True,
                autoscroll=False,
                elem_id="easy-prompt",
            )
            gr.Markdown(
                "Send the prepared messages instead of the original history in your next API request. "
                "You can also paste this into a new chat. Adding it to an existing long chat does not "
                "replace that chat's history."
            )
    with gr.Accordion("How this context was prepared", open=False):
        explanation = gr.Markdown()
        audit = gr.JSON(label="Sources and compilation details")
        messages = gr.JSON(label="Chat messages for your API client")
    outputs = [prompt, status, explanation, audit, messages]
    # Server responses stay hidden until the client compares their submitted inputs
    # with the current form. Cancelling a queued event alone cannot suppress a late
    # response from a synchronous function that already finished.
    received = [gr.Textbox(visible=False) for _ in range(3)] + [
        gr.JSON(visible=False),
        gr.JSON(visible=False),
    ]
    preparation = run.click(
        prepare_submission,
        [history, task, size],
        received,
        api_name="prepare",
        show_progress_on=status,
    )
    example_loading = try_example.click(
        quick_example,
        example,
        [history, task],
        api_name=False,
        cancels=[preparation],
    )
    demo_preparation = example_loading.success(
        prepare_submission, [history, task, size], received, api_name=False, show_progress_on=status
    )
    for event in (preparation, demo_preparation):
        event.success(
            fn=None, inputs=received, outputs=outputs, js=_PUBLISH_JS, queue=False
        ).success(
            fn=None,
            js="""() => { if (window.matchMedia('(max-width: 700px)').matches) {
                document.querySelector('#easy-status')?.scrollIntoView({
                    block: 'start', behavior: window.matchMedia('(prefers-reduced-motion: reduce)').matches ? 'instant' : 'smooth'
                });
            } }""",
        )
    pending = [preparation, example_loading, demo_preparation]
    for control in (history, task, size):
        control.input(fn=None, outputs=outputs, js=_CLEAR_JS, queue=False, cancels=pending)
    upload.upload(upload_text, upload, history, api_name=False, cancels=pending).success(
        fn=None, outputs=outputs, js=_CLEAR_JS, queue=False
    )
    load.click(quick_example, example, [history, task], api_name=False, cancels=pending).success(
        fn=None, outputs=outputs, js=_CLEAR_JS, queue=False
    )
    gr.Markdown(
        "This demo processes input on its host. Run TOMC locally to keep processing on your machine."
    )


def build_connect() -> None:
    """A short assistant handoff, with full client setup linked for maintainers."""
    gr.Markdown(
        "## Prepare context in your assistant\n\n"
        "Add TOMC to an assistant that supports MCP. Ask it to prepare task-specific context from "
        "the history you supply. TOMC runs before the reader request; it does not call a model. "
        "Use the returned context for a new chat or next API request. MCP cannot delete your "
        "assistant's existing chat history.\n\n"
        "You can optionally store notes and retrieve prepared context in a new chat:\n\n"
        "> “Save these workshop notes in TOMC as `workshop`.”\n\n"
        "> Next chat: “Recall `workshop` and help me continue.”\n\n"
        "From your TOMC checkout, install the optional tools:\n"
        "```bash\npython -m pip install -e '.[mcp]'\npython -m tomc setup --client codex\n```\n"
        "The second command prints your Codex configuration. Use `claude` or `cursor` to get their configuration instead.\n\n"
        "[Open the assistant setup guide](https://github.com/ZipengWu365/TOMC/blob/main/docs/assistant_setup.md)\n\n"
        "Notes are stored on the machine running your TOMC MCP server. The tools save the content you supply "
        "and return recalled text to your assistant, which handles that text under its provider's data policy. "
        "Set this up locally; the hosted demo only prepares context.\n\n"
        "MCP is one way to connect TOMC. For an API that accepts text context, call `prepare_context` "
        "and use `prepared.messages` in place of the original history in your own client. Keep the "
        "same model and inspect the input reduction for your task; savings vary with the history "
        "and budget. "
        "[Python and API examples](https://github.com/ZipengWu365/TOMC/blob/main/docs/quickstart.md)."
    )
