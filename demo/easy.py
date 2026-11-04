"""The first-use path: paste, describe the next task, copy into any model."""

from __future__ import annotations

import json
import re
import time
from html import escape
from importlib.resources import files

import gradio as gr

from tomc import compile_memory, prepare_context
from tomc.input import parse_history
from tomc.ledger import normalize
from tomc.tokenization import get_counter
from tomc.tryout import load_sample

# Smallest first. The first one is the budget `tomc try` uses for its sample.
SIZES = {"Small request": 200, "Compact": 512, "Balanced": 1024, "More detail": 4096}
SIZE_LABELS = {
    "zh": {
        "Small request": "小（200）",
        "Compact": "紧凑（512）",
        "Balanced": "均衡（1,024）",
        "More detail": "更多细节（4,096）",
    },
    "en": {
        "Small request": "Small (200)",
        "Compact": "Compact (512)",
        "Balanced": "Balanced (1,024)",
        "More detail": "More detail (4,096)",
    },
}

SAMPLE_EXAMPLE = "120-day project chat"
API_EXAMPLE = "Continue an API migration"
WORKSHOP_EXAMPLE = "Plan a workshop"
PREFERENCES_EXAMPLE = "Track changing preferences"
EXAMPLES = (SAMPLE_EXAMPLE, PREFERENCES_EXAMPLE, API_EXAMPLE, WORKSHOP_EXAMPLE)
EXAMPLE_LABELS = {
    "zh": {
        SAMPLE_EXAMPLE: "120 天项目聊天（内置样例，和 tomc try 同一份）",
        API_EXAMPLE: "接着做框架迁移",
        WORKSHOP_EXAMPLE: "安排一场工作坊",
        PREFERENCES_EXAMPLE: "跟踪改来改去的偏好（英文）",
    },
    "en": {
        SAMPLE_EXAMPLE: "120-day project chat (built-in sample, same as tomc try)",
        API_EXAMPLE: API_EXAMPLE,
        WORKSHOP_EXAMPLE: WORKSHOP_EXAMPLE,
        PREFERENCES_EXAMPLE: PREFERENCES_EXAMPLE,
    },
}

API_HISTORY = {
    "en": (
        "framework = Flask\n"
        "backup_framework copies framework\n"
        "framework = FastAPI\n"
        "Monday notes: the team reviewed the project backlog, discussed deployment windows and "
        "agreed to keep the public API routes and response fields unchanged during the refactor.\n"
        "Tuesday notes: the migration plan still needs a review from the database owner, and the "
        "pagination tests have not yet been written or run.\n"
        "Wednesday notes: the team checked the release checklist, added a rollback task, and "
        "postponed the documentation update until after the test results are available."
    ),
    "zh": (
        "framework = Flask\n"
        "backup_framework copies framework\n"
        "framework = FastAPI\n"
        "周一：大家过了一遍待办，聊了上线时间，说好重构期间公开接口的路径和返回字段都不动。\n"
        "周二：迁移方案还要数据库负责人看一眼，分页测试还没写，也还没跑。\n"
        "周三：对了一遍发布清单，加了一个回滚任务，文档等测试结果出来再改。"
    ),
}
API_TASK = {
    "en": "What are the current framework and backup_framework values?",
    "zh": "现在的 framework 和 backup_framework 分别是什么？",
}
WORKSHOP = {
    "en": (
        "Monday: The workshop is planned for 20 people.\n"
        "Tuesday: Attendance increased to 28. Two attendees need step-free access.\n"
        "Wednesday: Venue A has stairs. Venue B has a lift and holds 35 people.\n"
        "Venue B is available Friday afternoon. The room has not been booked yet.",
        "Which venue fits, and what still needs to be done?",
    ),
    "zh": (
        "周一：工作坊按 20 人准备。\n"
        "周二：报名涨到 28 人，其中两位需要无台阶通道。\n"
        "周三：A 场地只有楼梯；B 场地有电梯，能坐 35 人。\n"
        "B 场地周五下午有空，还没订。",
        "哪个场地合适？还有什么没做？",
    ),
}

T = {
    "zh": {
        "intro": "**打开页面时已经现场跑了一次**：下面是内置的 120 天项目聊天，"
        "和命令行 `tomc try` 用的是同一份样例、同一个函数、同一个预算。换成你自己的聊天记录，再点「准备」。",
        "history": "1. 聊天记录或笔记",
        "history_ph": "贴一段聊天记录或笔记。",
        "task": "2. 下一步要问什么",
        "task_ph": "比如：哪个场地合适？还有什么没做？",
        "run": "准备",
        "try": "换个例子",
        "more": "上传文件或选例子",
        "upload": "UTF-8 文本、Markdown、JSON 或 JSONL",
        "choose": "选一个例子",
        "load": "载入例子",
        "size_box": "带多少内容",
        "size": "预算（token）",
        "copy": "3. 把这段发给模型",
        "copy_note": "下次调用 API 时，用这段替换原来的历史；也可以贴进一个新聊天。"
        "贴进已经很长的旧聊天，不会删掉旧聊天里的内容。",
        "how": "这段内容是怎么准备的",
        "audit": "来源和处理细节",
        "messages": "给 API 客户端的消息",
        "host": "这个演示在它所在的机器上处理输入。想完全留在自己电脑上，就在本地运行 TOMC Memory。",
        "placeholder": "结果会出现在这里。",
        "changed": "输入改了，点「准备」重新算。",
        "strip_title": "原文 ↔ 交给模型的内容",
    },
    "en": {
        "intro": "**Already run once when the page opened**: this is the built-in 120-day project "
        "chat, the same sample, function and budget as `tomc try` on the command line. "
        "Paste your own history and click Prepare.",
        "history": "1. History",
        "history_ph": "Paste a conversation history or notes.",
        "task": "2. Next task",
        "task_ph": "For example: Which venue fits, and what still needs to be done?",
        "run": "Prepare",
        "try": "Next example",
        "more": "Upload or try an example",
        "upload": "UTF-8 text, Markdown, JSON or JSONL",
        "choose": "Choose an example",
        "load": "Load example",
        "size_box": "Memory size",
        "size": "Budget (tokens)",
        "copy": "3. Copy this into your model",
        "copy_note": "Send the prepared messages instead of the original history in your next API "
        "request. You can also paste this into a new chat. Adding it to an existing long chat "
        "does not replace that chat's history.",
        "how": "How this context was prepared",
        "audit": "Sources and compilation details",
        "messages": "Chat messages for your API client",
        "host": "This demo processes input on its host. Run TOMC Memory locally to keep "
        "processing on your machine.",
        "placeholder": "Your ready-to-use context appears here.",
        "changed": "Inputs changed. Prepare again.",
        "strip_title": "Original ↔ what the model gets",
    },
}

MINUS = "−"


def _lang(lang: str | None) -> str:
    return "zh" if (lang or "").startswith("zh") else "en"


def _key(name: str) -> str:
    """Accept an example key, a label, or an old 'English / 中文' style name."""
    head = name.split(" / ", 1)[0]
    for key in EXAMPLES:
        if head == key or any(head == labels[key] for labels in EXAMPLE_LABELS.values()):
            return key
    return WORKSHOP_EXAMPLE


def quick_example(name: str, lang: str = "en") -> tuple[str, str]:
    """Load examples as plain text, without requiring JSON knowledge."""
    lang, key = _lang(lang), _key(name)
    if key == SAMPLE_EXAMPLE:
        sample = load_sample(lang)
        return "\n".join(sample["lines"]), sample["question"]
    if key == API_EXAMPLE:
        return API_HISTORY[lang], API_TASK[lang]
    if key == PREFERENCES_EXAMPLE:
        data = json.loads(
            files("tomc").joinpath("data/preferences.json").read_text(encoding="utf-8")
        )
        return "\n\n".join(m["content"] for m in data["messages"]), data["query"]
    return WORKSHOP[lang]


def message_content_counts(
    before: list[dict[str, str]], after: list[dict[str, str]]
) -> tuple[int, int]:
    """Count all message text with one estimator, excluding provider framing."""
    counter = get_counter("regex")
    return tuple(sum(counter.count(m["content"]) for m in messages) for messages in (before, after))


def _percent(saved: int, before: int) -> int:
    value = round(100 * abs(saved) / before)
    return 1 if value == 0 and saved else value


def input_reduction(before: int, after: int, lang: str = "en") -> str:
    """One plain headline: a reduction always uses '−', an increase is said plainly."""
    lang = _lang(lang)
    saved = before - after
    if not before:
        return "无法计算：没有输入" if lang == "zh" else "Change not defined: empty input"
    if saved > 0:
        pct = _percent(saved, before)
        return (
            f"少发 {saved:,} token（{MINUS}{pct}%）"
            if lang == "zh"
            else f"{saved:,} fewer tokens ({MINUS}{pct}%)"
        )
    if saved < 0:
        pct = _percent(saved, before)
        return (
            f"上下文增加了 {-saved:,} token（+{pct}%）"
            if lang == "zh"
            else f"Context grew by {-saved:,} tokens (+{pct}%)"
        )
    return "没有变化（0%）" if lang == "zh" else "No change (0%)"


_SOURCE_IDS = re.compile(r"<src:([^>]+)>|\[RAW (u\d+)\]|\(later: (u\d+)\)")
_STATE = re.compile(r"^\[STATE(\??)\] (\S+) = (.+?)(?:\s+\(later: (u\d+)\))?\s+<src:([^>]+)>$")
_RAW = re.compile(r"^\[RAW (u\d+)\] (.*)$")


def _where(unit, single: bool, lang: str) -> str:
    if single:
        return f"第 {unit.line_number:,} 行" if lang == "zh" else f"line {unit.line_number:,}"
    return (
        f"第 {unit.message_index + 1} 条第 {unit.line_number} 行"
        if lang == "zh"
        else f"msg {unit.message_index + 1}, line {unit.line_number}"
    )


def _num(unit, single: bool) -> str:
    return f"{unit.line_number:,}" if single else f"{unit.message_index + 1}:{unit.line_number}"


def found_records(memory: str, units: list, lang: str = "en", task: str = "") -> list[str]:
    """The current values the prepared memory carries, each with its source lines.

    Rows follow the order the task names them in, like `tomc try`.
    """
    by_id = {u.source_id: u for u in units}
    single = len({u.message_index for u in units}) <= 1
    join = "、" if lang == "zh" else ", "
    rows = []
    for line in memory.splitlines():
        match = _STATE.match(line.strip())
        if not match:
            continue
        doubtful, key, value, later, sources = match.groups()
        position = task.find(key)
        cited = [by_id[s.strip()] for s in sources.split(",") if s.strip() in by_id]
        where = join.join(_where(u, single, lang) for u in cited)
        row = f"<code>{escape(key)} = {escape(value)}</code>"
        if where:
            row += f' <span class="src">← {escape(where)}</span>'
        if doubtful and later in by_id:
            row += (
                f' <span class="doubt">（{escape(_where(by_id[later], single, lang))}可能改过，已附原句）</span>'
                if lang == "zh"
                else f' <span class="doubt">({escape(_where(by_id[later], single, lang))} may have changed it; included)</span>'
            )
        rows.append((position < 0, position, key, row))
    return [row for *_, row in sorted(rows)]


def source_strip(parsed: object, result, lang: str = "en") -> str:
    """Original lines beside the prepared memory; every kept line shows where it came from."""
    lang = _lang(lang)
    _, units = normalize(parsed)
    memory = result.compiled_memory
    if not memory:
        return ""
    if result.diagnostics.get("selected_strategy") == "raw":
        text = (
            "历史放得下：整段原样交给模型，一行都没删。"
            if lang == "zh"
            else "The history fits: the model gets all of it, nothing removed."
        )
        return f'<div class="strip-note">{text}</div>'
    by_id = {u.source_id: u for u in units}
    single = len({u.message_index for u in units}) <= 1
    kept, key_ids = set(), set()
    for match in _SOURCE_IDS.finditer(memory):
        ids = [s.strip() for s in (match[1] or match[2] or match[3]).split(",")]
        kept.update(ids)
        if match[1]:
            key_ids.update(ids)
    left, gap = [], 0

    def flush_gap() -> None:
        nonlocal gap
        if gap:
            text = (
                f"⋯ {gap:,} 行没带上"
                if lang == "zh"
                else f"⋯ {gap:,} line{'s' if gap > 1 else ''} left out"
            )
            left.append(f'<div class="gap">{text}</div>')
            gap = 0

    for unit in units:
        if unit.source_id not in kept:
            gap += 1
            continue
        flush_gap()
        cls = "key" if unit.source_id in key_ids else "kept"
        left.append(
            f'<div class="ln {cls}"><b>{_num(unit, single)}</b><span>{escape(unit.text)}</span></div>'
        )
    flush_gap()
    right = []
    for line in memory.splitlines():
        state, raw = _STATE.match(line.strip()), _RAW.match(line.strip())
        if state:
            doubtful, key, value, _later, sources = state.groups()
            nums = ",".join(
                _num(by_id[s.strip()], single) for s in sources.split(",") if s.strip() in by_id
            )
            mark = "?" if doubtful else ""
            right.append(
                f'<div class="ln key"><b>{escape(nums)}</b><span><code>{escape(key)} = '
                f"{escape(value)}</code>{mark}</span></div>"
            )
        elif raw and raw[1] in by_id:
            right.append(
                f'<div class="ln kept"><b>{_num(by_id[raw[1]], single)}</b>'
                f"<span>{escape(raw[2])}</span></div>"
            )
        elif line.strip():
            right.append(f'<div class="ln"><b></b><span>{escape(line)}</span></div>')
    total, kept_count = len(units), sum(1 for u in units if u.source_id in kept)
    if lang == "zh":
        head_l = f"原文 · {total:,} 行（非空）"
        head_r = f"交给模型的 · 带上 {kept_count:,} 行原文"
        legend = "每一行左边的数字是它在原文里的行号。深色：当前值的出处；浅色：一起带上的原句。"
    else:
        head_l = f"Original · {total:,} non-empty lines"
        head_r = f"What the model gets · {kept_count:,} source lines kept"
        legend = (
            "The number on each line is its line in the original. Dark: where a current value "
            "comes from; light: source text kept alongside."
        )
    return (
        '<div class="strip">'
        f'<div class="strip-col"><h4>{head_l}</h4><div class="strip-scroll">{"".join(left)}</div></div>'
        f'<div class="strip-col"><h4>{head_r}</h4><div class="strip-scroll">{"".join(right)}</div></div>'
        f'</div><p class="strip-legend">{legend}</p>'
    )


def _card(
    headline: str, change: int, sub: str, found: list[str], fine: list[str], lang: str
) -> str:
    est = "估算 ⓘ" if lang == "zh" else "estimate ⓘ"
    hint = (
        "token 数是本地估算，不是账单。点开看口径。"
        if lang == "zh"
        else "Token counts are local estimates, not a bill. Click for details."
    )
    tone = "down" if change > 0 else ("up" if change < 0 else "flat")
    label = "找到当前值：" if lang == "zh" else "Current values found:"
    found_html = (
        f'<div class="found"><span>{label}</span><ul>'
        + "".join(f"<li>{row}</li>" for row in found)
        + "</ul></div>"
        if found
        else ""
    )
    return (
        f'<details class="result-card {tone}"><summary>'
        f'<div class="big"><strong>{escape(headline)}</strong>'
        f'<span class="est" title="{escape(hint)}">· {est}</span></div>'
        f'<div class="sub">{sub}</div>{found_html}</summary>'
        f'<ul class="fine">{"".join(f"<li>{x}</li>" for x in fine)}</ul></details>'
    )


def prepare_view(history: str, task: str, size: str, lang: str = "en") -> tuple:
    """Return the prompt, a headline card, notes, audit data, messages and a source strip."""
    lang = _lang(lang)
    try:
        started = time.perf_counter()
        prepared = prepare_context(history, task, SIZES[size.split(" / ", 1)[0]])
        seconds = time.perf_counter() - started
    except (ValueError, TypeError, KeyError) as exc:
        hints = {
            "en": {
                "Describe what you want the model to do next.": "Add your next task, for example: Which venue fits, and what still needs to be done?",
                "Paste a history or load an example first.": "Paste your history or click Try demo to prepare a sample.",
                "Use at most 200,000 characters per history.": "Shorten the history or split it into smaller batches of up to 200,000 characters.",
            },
            "zh": {
                "Describe what you want the model to do next.": "写上下一步要问什么，比如：哪个场地合适？还有什么没做？",
                "Paste a history or load an example first.": "先贴一段聊天记录，或者点「换个例子」。",
                "Use at most 200,000 characters per history.": "一次最多 20 万字符。删短一点，或者分几次处理。",
            },
        }[lang]
        message = str(exc)
        fallback = (
            f"{message} 请检查输入；JSON 和 JSONL 需要是文字消息。"
            if lang == "zh"
            else f"{message} Check your input; JSON and JSONL need text messages."
        )
        raise gr.Error(hints.get(message, fallback)) from None
    result = prepared.compilation
    stats = result.stats
    parsed = parse_history(history)
    raw = compile_memory(parsed, task.strip(), stats.token_budget, "raw")
    before, after = message_content_counts(raw.reader_messages(task.strip()), prepared.messages)
    elapsed = (
        ("不到 0.01 秒" if lang == "zh" else "under 0.01 s")
        if seconds < 0.01
        else (f"{seconds:.2f} 秒" if lang == "zh" else f"{seconds:.2f} s")
    )
    units = normalize(parsed)[1]
    if not prepared.prompt:
        if lang == "zh":
            headline = "放不下：预算太小"
            sub = (
                "这个预算装不下一整行原文或一条记录。把长段落拆成短行，或者在「带多少内容」里选大一点。"
                "已经选了「更多细节」的话，就在句子之间加换行。"
            )
        else:
            headline = "No complete record fits"
            sub = (
                "Unusable request: this budget cannot fit a complete source line or record. Break long paragraphs "
                "into shorter lines, or choose a larger memory size. If More detail is already "
                "selected, add line breaks between sentences. Increase the memory size before "
                "sending it."
            )
        change, found = 0, []
    else:
        headline = input_reduction(before, after, lang)
        change = before - after
        found = found_records(result.compiled_memory, units, lang, task)
        if lang == "zh":
            sub = (
                f"整段请求 {before:,} → {after:,} token · 预算 {stats.token_budget:,} · "
                f"{elapsed}，只用本机 CPU，不调用模型"
            )
            if change == 0 and result.diagnostics.get("selected_strategy") == "raw":
                sub += " · 历史放得下，原样发送，不需要压缩"
            elif change < 0:
                sub += " · 很短的历史加上来源标签会变长，这种情况直接发原文就行"
        else:
            sub = (
                f"Whole request {before:,} → {after:,} tokens · budget {stats.token_budget:,} · "
                f"{elapsed}, local CPU, no model call"
            )
            if change == 0 and result.diagnostics.get("selected_strategy") == "raw":
                sub += " · the history fits; no compression was needed"
            elif change < 0:
                sub += " · source labels make a very short history longer; send the original"
    if lang == "zh":
        fine = [
            "token 数是本地估算（两边用同一个计数器），不是账单，也不是模型实际计费。",
            "左边是把整段历史原样发出去，右边是 TOMC Memory 准备后的内容。两边都带同样的系统说明和问题；"
            "不含服务商的消息封装、工具定义和隐藏 token。",
            f"只看历史部分：{stats.input_tokens:,} → {stats.output_tokens:,} token（预算 {stats.token_budget:,}）。",
            "数字是点「准备」（或打开页面）时用同一个函数现场算的，没有预先写好。",
        ]
    else:
        fine = [
            "Token counts are local estimates (one counter for both sides), not measured API usage or a bill.",
            "Before: the whole history sent as is. After: what TOMC Memory prepared. Both include the "
            "same system instructions and task; provider framing, tool schemas and hidden tokens are excluded.",
            f"Memory only: {stats.input_tokens:,} → {stats.output_tokens:,} tokens "
            f"(budget {stats.token_budget:,}). {escape(prepared.note)}",
            "Computed live with the same function when you click Prepare (or open the page).",
        ]
    status = _card(headline, change, sub, found, fine, lang)
    if lang == "zh":
        explanation = (
            f"**用的方法：** `{result.diagnostics['selected_strategy']}`。"
            f"{result.diagnostics['route_reason']}\n\n"
            "放得下的历史整段保留。更长的历史按固定规则选方法：有明确赋值的（如 `framework = FastAPI`）"
            "整理成「当前值 + 出处」，普通文字就挑出相关的原句。这里不调用任何模型，"
            "答案由你之后把这段交给的模型给出。"
        )
    else:
        explanation = (
            f"**Selected method:** `{result.diagnostics['selected_strategy']}`. "
            f"{result.diagnostics['route_reason']}\n\n"
            "Histories that fit are kept whole. For longer input, fixed rules select a method; "
            "ordinary prose uses retrieval of original text. Your model answers after you pass it "
            "this context.\n\n"
            "For the next API request, use these prepared messages in place of the original "
            "history. Appending this result to an existing long chat does not remove that chat's "
            "history."
        )
    strip = source_strip(parsed, result, lang) if prepared.prompt else ""
    return prepared.prompt, status, explanation, result.to_dict(), prepared.messages, strip


def prepare_submission(history: str, task: str, size: str, lang: str = "en") -> tuple:
    """Keep the submitted inputs beside a result until the browser checks freshness."""
    prompt, status, explanation, audit, messages, strip = prepare_view(history, task, size, lang)
    return (
        prompt,
        status,
        explanation,
        {**audit, "_submitted_inputs": [history, task, size]},
        messages,
        strip,
    )


def _clear_js(lang: str) -> str:
    note = json.dumps(f'<div class="result-wait">{T[lang]["changed"]}</div>')
    return f'() => ["", {note}, "", {{}}, [], ""]'


def _publish_js(lang: str) -> str:
    return (
        r"""(prompt, status, explanation, audit, messages, strip) => {
    const submitted = audit?._submitted_inputs;
    const history = document.querySelector('#easy-history-LANG textarea')?.value;
    const task = document.querySelector('#easy-task-LANG textarea')?.value;
    const size = document.querySelector('#easy-size-LANG input:checked')?.value;
    const normalize = value => value?.replace(/\r\n?/g, "\n");
    if (!submitted || normalize(submitted[0]) !== normalize(history) || normalize(submitted[1]) !== normalize(task) || submitted[2] !== size) {
        return Array.from({length: 6}, () => ({__type__: "update"}));
    }
    const cleanAudit = {...audit};
    delete cleanAudit._submitted_inputs;
    return [prompt, status, explanation, cleanAudit, messages, strip];
}"""
    ).replace("LANG", lang)


# Kept for callers that imported the English versions.
_CLEAR_JS = _clear_js("en")
_PUBLISH_JS = _publish_js("en")


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


def first_result(lang: str = "zh") -> tuple:
    """The page opens on the built-in sample, prepared live with the default budget."""
    history, task = quick_example(SAMPLE_EXAMPLE, lang)
    return (history, task, *prepare_view(history, task, next(iter(SIZES)), lang))


def build_easy(lang: str = "en", primary: bool = True) -> None:
    """Two inputs and one main action; the result is already there on page load."""
    lang = _lang(lang)
    t = T[lang]
    history0, task0, prompt0, status0, explanation0, audit0, messages0, strip0 = first_result(lang)
    gr.Markdown(t["intro"], elem_classes="easy-intro")
    with gr.Row(equal_height=False, elem_classes="easy-row"):
        with gr.Column(scale=5, min_width=300, elem_classes="easy-result"):
            status = gr.HTML(status0, elem_id=f"easy-status-{lang}")
            strip = gr.HTML(strip0, elem_id=f"easy-strip-{lang}")
        with gr.Column(scale=4, min_width=300, elem_classes="easy-inputs"):
            history = gr.Textbox(
                value=history0,
                label=t["history"],
                placeholder=t["history_ph"],
                lines=5,
                max_lines=8,
                elem_id=f"easy-history-{lang}",
            )
            task = gr.Textbox(
                value=task0,
                label=t["task"],
                placeholder=t["task_ph"],
                lines=2,
                elem_id=f"easy-task-{lang}",
            )
            with gr.Row():
                run = gr.Button(t["run"], variant="primary", elem_id=f"easy-run-{lang}", scale=3)
                try_example = gr.Button(
                    t["try"], elem_id=f"easy-try-{lang}", scale=1, min_width=110
                )
            with gr.Accordion(t["more"], open=False):
                upload = gr.File(
                    label=t["upload"],
                    file_types=[".txt", ".md", ".json", ".jsonl"],
                    type="binary",
                    elem_id=f"easy-upload-{lang}",
                )
                example = gr.Dropdown(
                    [(EXAMPLE_LABELS[lang][key], key) for key in EXAMPLES],
                    label=t["choose"],
                    value=SAMPLE_EXAMPLE,
                )
                load = gr.Button(t["load"])
            with gr.Accordion(t["size_box"], open=False):
                size = gr.Radio(
                    [(SIZE_LABELS[lang][key], key) for key in SIZES],
                    value=next(iter(SIZES)),
                    label=t["size"],
                    elem_id=f"easy-size-{lang}",
                )
    prompt = gr.Textbox(
        value=prompt0,
        label=t["copy"],
        lines=6,
        max_lines=14,
        interactive=False,
        show_copy_button=True,
        autoscroll=False,
        elem_id=f"easy-prompt-{lang}",
    )
    gr.Markdown(t["copy_note"], elem_classes="small-note")
    with gr.Accordion(t["how"], open=False):
        explanation = gr.Markdown(explanation0)
        audit = gr.JSON(audit0, label=t["audit"])
        messages = gr.JSON(messages0, label=t["messages"])
    outputs = [prompt, status, explanation, audit, messages, strip]

    def submit(history: str, task: str, size: str) -> tuple:
        return prepare_submission(history, task, size, lang)

    def example_text(name: str) -> tuple[str, str]:
        return quick_example(name, lang)

    def next_example(name: str) -> tuple[str, str, str]:
        key = EXAMPLES[(EXAMPLES.index(_key(name or SAMPLE_EXAMPLE)) + 1) % len(EXAMPLES)]
        return (key, *quick_example(key, lang))

    # Server responses stay hidden until the client compares their submitted inputs
    # with the current form. Cancelling a queued event alone cannot suppress a late
    # response from a synchronous function that already finished.
    received = [gr.Textbox(visible=False) for _ in range(3)] + [
        gr.JSON(visible=False),
        gr.JSON(visible=False),
        gr.Textbox(visible=False),
    ]
    preparation = run.click(
        submit,
        [history, task, size],
        received,
        api_name="prepare" if primary else False,
        show_progress_on=status,
    )
    example_loading = try_example.click(
        next_example, example, [example, history, task], api_name=False, cancels=[preparation]
    )
    demo_preparation = example_loading.success(
        submit, [history, task, size], received, api_name=False, show_progress_on=status
    )
    for event in (preparation, demo_preparation):
        event.success(
            fn=None, inputs=received, outputs=outputs, js=_publish_js(lang), queue=False
        ).success(
            fn=None,
            js=f"""() => {{ if (window.matchMedia('(max-width: 700px)').matches) {{
                document.querySelector('#easy-status-{lang}')?.scrollIntoView({{
                    block: 'start', behavior: window.matchMedia('(prefers-reduced-motion: reduce)').matches ? 'instant' : 'smooth'
                }});
            }} }}""",
        )
    pending = [preparation, example_loading, demo_preparation]
    clear = _clear_js(lang)
    for control in (history, task, size):
        control.input(fn=None, outputs=outputs, js=clear, queue=False, cancels=pending)
    upload.upload(upload_text, upload, history, api_name=False, cancels=pending).success(
        fn=None, outputs=outputs, js=clear, queue=False
    )
    load.click(example_text, example, [history, task], api_name=False, cancels=pending).success(
        fn=None, outputs=outputs, js=clear, queue=False
    )
    gr.Markdown(t["host"], elem_classes="small-note")


CONNECT = {
    "en": (
        "## Prepare context in your assistant\n\n"
        "Add TOMC Memory to an assistant that supports MCP (Codex, Claude Code and others). Ask it "
        "to prepare task-specific context from the history you supply. TOMC Memory runs before "
        "the model request; it does not call a model. Use the returned context for a new chat or "
        "your next API request. MCP cannot delete your assistant's existing chat history.\n\n"
        "You can optionally store notes and retrieve prepared context in a new chat:\n\n"
        "> “Save these workshop notes in TOMC Memory as `workshop`.”\n\n"
        "> Next chat: “Recall `workshop` and help me continue.”\n\n"
        "From your TOMC checkout, install the optional tools:\n"
        "```bash\npython -m pip install -e '.[mcp]'\npython -m tomc setup --client codex --write\n"
        "python -m tomc doctor\n```\n"
        "The second command adds TOMC Memory to your Codex configuration and backs the file up "
        "first. Use `claude-desktop`, `claude-code`, `cursor` or `workbuddy` for those clients. "
        "Then start a new chat and say “Try TOMC Memory”.\n\n"
        "[Open the assistant setup guide](https://github.com/ZipengWu365/TOMC/blob/main/docs/assistant_setup.md)\n\n"
        "Notes you save are stored on the computer that runs your TOMC MCP server. Prepared "
        "results are not saved unless you turn that on. Recalled text goes to your assistant, "
        "which handles it under its provider's data policy. This demo only prepares context; "
        "it saves no notes.\n\n"
        "MCP is one way to connect. For an API that accepts text context, call `prepare_context` "
        "and use `prepared.messages` in place of the original history in your own client. Keep the "
        "same model and check the input reduction for your task; savings vary with the history "
        "and budget. "
        "[Python and API examples](https://github.com/ZipengWu365/TOMC/blob/main/docs/quickstart.md)."
    ),
    "zh": (
        "## 在助手里直接用\n\n"
        "把 TOMC Memory 接到支持 MCP 的助手上（Codex、Claude Code 等）。之后让助手用它整理你给的聊天记录，"
        "只留下这次要用的内容。TOMC Memory 在调用模型之前运行，自己不调用模型。整理好的内容可以用在新聊天里，"
        "或者下一次 API 调用里。MCP 删不掉助手里已有的聊天记录。\n\n"
        "也可以把笔记存起来，在新聊天里再取出来：\n\n"
        "> 「用 TOMC Memory 把这份工作坊笔记存成 `workshop`。」\n\n"
        "> 下次新聊天：「取出 `workshop`，接着上次做。」\n\n"
        "在 TOMC 的代码目录里安装：\n"
        "```bash\npython -m pip install -e '.[mcp]'\npython -m tomc setup --client codex --write\n"
        "python -m tomc doctor\n```\n"
        "第二条命令会先备份 Codex 的配置文件，再把 TOMC Memory 加进去。其他助手把 `codex` 换成 "
        "`claude-desktop`、`claude-code`、`cursor` 或 `workbuddy`。然后开一个新聊天，说「试试 TOMC Memory」。\n\n"
        "[助手接入说明（英文）](https://github.com/ZipengWu365/TOMC/blob/main/docs/assistant_setup.md)\n\n"
        "存下的笔记只放在运行 TOMC MCP 的那台电脑上。整理结果默认不保存。取出的内容会交给你的助手，"
        "按它自己的数据政策处理。这个演示页只整理，不存任何笔记。\n\n"
        "不用 MCP 也行：直接调用 `prepare_context`，在你自己的程序里用 `prepared.messages` 替换原来的历史。"
        "模型不用换。能少发多少要看你的历史和预算，用自己的任务试一下。"
        "[Python 和 API 示例（英文）](https://github.com/ZipengWu365/TOMC/blob/main/docs/quickstart.md)"
    ),
}


def build_connect(lang: str = "en") -> None:
    """A short assistant handoff, with full client setup linked for maintainers."""
    gr.Markdown(CONNECT[_lang(lang)])
