# TOMC publication copy — 11 October 2026

Author: Zipeng Wu · GitHub: zipengwu365 · Product: TOMC Memory

Status: ready-to-review copy. None of the social posts below has been published or scheduled by this task. The linked website guides are published separately. Verify each platform's current community rules before submitting.

## Shared links and media

- Product: https://github.com/ZipengWu365/TOMC
- Recorded example explorer: https://zipengwu.me/tomc/examples/
- Guides: https://zipengwu.me/tomc/guides/
- Source and installation: https://github.com/ZipengWu365/TOMC
- Native Claude Code plugin: https://github.com/ZipengWu365/TOMC-plugin
- Current English landscape video: https://github.com/ZipengWu365/TOMC/blob/main/launch/media/v12/videos/TOMC_Agent_Complete_EN.mp4
- English landscape cover: https://github.com/ZipengWu365/TOMC/blob/main/launch/media/v12/covers/TOMC_Agent_Complete_EN.png
- Media scope: https://github.com/ZipengWu365/TOMC/blob/main/launch/media/v12/MODEL_TEST_SCOPE_v12.md

Use the existing landscape format. The new website explorer contains recorded outputs, not a live compiler or LLM. Do not caption it as a live model test. Provider names describe supported or tested workflows within the linked scope, not endorsement.

## X post 1 — product introduction

TOMC prepares task-specific context on CPU for your existing LLM. Inspect the retained evidence, then use it in the next request. No extra model service.

TOMC Memory
https://zipengwu.me/tomc/examples/

## X post 2 — handoff

New chat, same project. TOMC lets Codex and Claude Code reuse explicitly saved notes through one shared local notebook.

Setup + a three-step example:
https://zipengwu.me/tomc/guides/shared-task-memory/

TOMC Memory

## X post 3 — measurement

A smaller memory is only one measurement. Check the full request, answer quality and every model call in the workflow.

My TOMC evaluation guide:
https://zipengwu.me/tomc/guides/measure-context-savings/

TOMC Memory

## X post 4 — specific example

framework = Flask
backup_framework copies framework
framework = FastAPI

The backup still holds Flask. Inspect how TOMC represents this update chain at three budgets:
https://zipengwu.me/tomc/examples/

TOMC Memory

## Paid creative A — context preparation

Long history, one next task. TOMC prepares context locally on CPU for your existing LLM. Inspect real recorded outputs, then try the Python API.

TOMC Memory

Destination: https://github.com/ZipengWu365/TOMC?utm_source=x&utm_medium=paid_social&utm_campaign=tomc_pilot_100&utm_content=context_a

Media: existing English landscape video, linked above. Do not turn an example's count into a universal percentage claim.

## Paid creative B — project continuity

Keep your project notes when you start a new chat. TOMC supports explicit save and recall across Codex and Claude Code with a shared local notebook.

TOMC Memory

Destination: https://github.com/ZipengWu365/TOMC?utm_source=x&utm_medium=paid_social&utm_campaign=tomc_pilot_100&utm_content=handoff_b

Media: the same landscape video for the first comparison. The initial test changes the message, not every creative element at once.

## LinkedIn post

I have published TOMC Memory, an open-source project for context compression and task memory with existing LLMs.

There are two workflows I wanted to make easier to inspect.

First, prepare a long history for a specific next question. TOMC selects source text and computes records for supported state, relation and count operations on CPU. The application can send the prepared context to its existing model.

Second, carry explicit project notes into a new session. With Codex and Claude Code configured to use the same local TOMC notebook, you can save constraints and unfinished work, then recall them for the next task. Continuing with the same assistant is also supported.

I have added three practical guides and an example explorer. The explorer shows nine recorded outputs from the actual implementation, including a short history that stays unchanged. It makes no model calls and is not an answer-quality benchmark.

The current parser and retrieval use fixed rules. Results depend on the task and input, and calling a tool does not erase history already in an active chat. The guides explain how to measure complete requests and inspect omissions.

Try it: https://github.com/ZipengWu365/TOMC
Source: https://github.com/ZipengWu365/TOMC

I would particularly welcome synthetic examples where the prepared context misses a fact needed for the next question.

TOMC Memory

## Show HN submission

Title: Show HN: TOMC — CPU context compression and local task memory

Submit URL: https://github.com/ZipengWu365/TOMC

First comment:

I'm Zipeng Wu, the author of TOMC. I built it to prepare task-specific context on CPU before an existing LLM answers, and to reuse explicitly saved project notes across sessions.

The Python API takes history, task and budget. It returns ordinary text or chat messages; construction requires no model weights or extra neural service. Local MCP tools add explicit notebook save and recall, including a shared-database workflow for Codex and Claude Code.

The source is MIT-licensed and runnable locally. A small recorded-output explorer is here: https://zipengwu.me/tomc/examples/ . It lets you compare three histories at three budgets; it does not run a live model. The API guide includes a local example with no reader call: https://zipengwu.me/tomc/guides/context-compression-api/ .

The limitations matter. The built-in parser recognizes explicit operations, and routing/retrieval use lexical rules. Paraphrases and implicit updates can be missed. A tiny history can remain unchanged or grow after framing, and a tool call inside a long chat does not remove earlier host messages.

I'm interested in small synthetic histories where the representation fails, and in whether the installation and handoff steps are clear enough for a first-time user.

Publication condition: the author should be available to answer questions. Link to runnable software. Do not ask friends for votes. Source: https://news.ycombinator.com/showhn.html

## Developer-community post

Title: I built a CPU context-preparation tool and a local task-notebook workflow for AI assistants

I'm the author of TOMC Memory. It prepares task-specific context from supplied history and returns text for an existing LLM. It also exposes local MCP notebook tools for explicitly saving and recalling project notes.

One example is an update chain where a backup copies a value before the current value changes. Another is a same-computer handoff: save API constraints in Codex, recall them in Claude Code, append a test plan, then return to Codex. Both clients must use the same database.

I have posted a runnable API tutorial and a recorded-output explorer:
https://zipengwu.me/tomc/guides/
https://zipengwu.me/tomc/examples/

The explorer uses real local compiler outputs on synthetic inputs. It makes no LLM calls. The reference parser has explicit syntax and lexical limitations; this is research software, and there is no universal saving percentage.

If you try it, a useful report is the synthetic input, next task, budget, expected fact and actual retained context. Please leave private conversations out of public reports.

Source: https://github.com/ZipengWu365/TOMC
TOMC Memory

## Replies

Does installation automatically cut every request? No. Your application must adopt the prepared messages, or a new chat must receive the prepared text. Tool use can add requests.

Does it need another LLM? CPU context preparation does not. Your selected reader still generates the answer under its usual provider terms.

Does it synchronize all my chats? No. Explicit notes can be shared through the same local notebook. Cross-device transfer is manual in the current preview.

Is the website explorer live inference? No. It shows recorded outputs from the actual Python code. The source and local execution instructions are linked.

Where can I find it without a link? Search for “zipengwu365 TOMC”.
