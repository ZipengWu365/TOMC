# TOMC Memory | A cat that saves you tokens—keep working across code agents and computers

**Keep your token-saving cat happy. 🐱**

I built a desktop cat for TOMC. Give it your scattered context and watch it smile as it gathers the notes and prepares task memory. Click the cat to see context savings, task notes, and saved contexts. It has four animated forms: larger contexts bring a higher-tier look, up to a crowned cat with a desert-to-oasis animation. Save tokens, with a little cat-keeping fun on your desktop.

![The crowned TOMC cat and its desert-to-oasis animation](https://raw.githubusercontent.com/ZipengWu365/TOMC/84e96165fe9b96aaaf52bf3729b755286670ba93/docs/assets/workbuddy/cat-oasis.gif)

*Animation from the actual desktop companion. Forms follow the current context length. [Install the desktop cat](https://github.com/ZipengWu365/TOMC/blob/main/docs/desktop_companion.md).*

Hi everyone, I’m the author of TOMC and a DeepSeek API user, with over **128 million tokens** used so far. Our research explores task-oriented context compression: turning long histories into compact memory that helps a model complete its task with less input.

We evaluated TOMC on **BEAM**, covering **100K, 500K, 1M, and 10M-token histories**, against six baselines: **LLMLingua-2, hierarchical LLMLingua-2, LongLLMLingua, BRIEF-Pro, BEAM-RAG, and LIGHT**. Our evaluation covered **2,000 questions**; see the [experimental results in our GitHub repository](https://github.com/ZipengWu365/TOMC#same-reader-baseline-memory-vs-tomc-memory). Across the **18 overall comparisons involving three answering models and six baselines, TOMC achieved higher mean task scores in every comparison**. Overall model input was approximately **36.6% lower than LIGHT’s**.

I turned this research into **TOMC Memory**, an open-source tool with three practical features:

1. **Reduce input:** Compress and prepare task context locally on CPU, without an additional LLM or GPU.
2. **Switch code agents:** Save project requirements, decisions, and unfinished work so another agent connected to the same memory database can continue. Integration options are available for **Codex, Claude Code, Cursor, TRAE, Tencent WorkBuddy, Claude Desktop, and DeepSeek Harness**.
3. **Switch computers:** Export your task notes and bring them to another computer without explaining the project from scratch.

We have run real-model tests in Codex and Claude Code. In the Codex test across nine synthetic project histories, complete request input decreased by **29.7%** on average, while both the full-history and compressed conditions answered **45/45 questions correctly**. We have also tested saving notes, recalling them in a fresh session, and continuing a task in **DeepSeek Harness and WorkBuddy**. With **GLM-5.3-Flash in WorkBuddy**, a new task recalled **4/4 project facts correctly** and used them to produce a release checklist. [Test records](https://github.com/ZipengWu365/TOMC/blob/84e96165fe9b96aaaf52bf3729b755286670ba93/docs/validation.md)

A friend has also used TOMC for social content, video production, and research slides. His contributed report records **5.16% fewer total model tokens** for a Xiaohongshu content project and **16.84% fewer** for research slides and revisions. [Community case studies](https://github.com/ZipengWu365/TOMC/blob/main/casestudy/README.md)

TOMC is listed on multiple MCP platforms, including **[Odel](https://odel.app/modules/zipengwu365/tomc-memory), [MCP Harbor](https://www.mcpharbor.app/tools/zipengwu365-tomc/), and [ProtocolProbe](https://protocolprobe.com/mcp/servers/io.github.ZipengWu365/tomc-memory)**, and is also available in the **[SkillsLLM](https://skillsllm.com/skill/tomc)** and **[AugmentClaude](https://augmentclaude.com/s/tomc-memory-zipengwu365)** directories. I’d like to bring this research and tool to the MCP community and hear how it works on your longer-running tasks.

[Source code](https://github.com/ZipengWu365/TOMC) · [Installation guide](https://github.com/ZipengWu365/TOMC/blob/84e96165fe9b96aaaf52bf3729b755286670ba93/docs/workbuddy.md) · [Desktop cat](https://github.com/ZipengWu365/TOMC/blob/main/docs/desktop_companion.md)

![Four native cat animation forms](https://raw.githubusercontent.com/ZipengWu365/TOMC/84e96165fe9b96aaaf52bf3729b755286670ba93/docs/assets/workbuddy/cat-four-forms.gif)

*Unofficial, open-source community plugin.*

### Live model evidence

[Full WorkBuddy validation report](https://github.com/ZipengWu365/TOMC/blob/84e96165fe9b96aaaf52bf3729b755286670ba93/docs/workbuddy_validation_20261029.md) — WorkBuddy 5.8.2, GLM-5.3-Flash: 10 tools connected; save, fresh-task recall (4/4 facts), and continuation passed.

![Fresh-task recall: all four project facts correct](https://raw.githubusercontent.com/ZipengWu365/TOMC/84e96165fe9b96aaaf52bf3729b755286670ba93/docs/assets/workbuddy/workbuddy-recall.png)

![Continuing the task from recalled project notes](https://raw.githubusercontent.com/ZipengWu365/TOMC/84e96165fe9b96aaaf52bf3729b755286670ba93/docs/assets/workbuddy/workbuddy-checklist.png)

[DeepSeek Harness live validation](https://github.com/ZipengWu365/TOMC/blob/main/docs/deepseek_harness_validation_20261029.md) · [Installation and client test records](https://github.com/ZipengWu365/TOMC/blob/84e96165fe9b96aaaf52bf3729b755286670ba93/docs/validation.md)
