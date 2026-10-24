# Prompt caching and TOMC — 2026-10-17

[中文](prompt_cache_20261017_zh.md) · [Request policy](context_ownership.md)

Providers bill a repeated request prefix at a reduced cached price. A reader pointed out that rewriting history can break that cache. We measured both sides and changed the default `AutomaticChatSession` policy.

## Live Claude measurement

Claude Code 2.1.301 in headless mode, model `claude-haiku-5-5`, costs as reported by Claude Code at list prices, including cache writes and reads. Three synthetic histories of about 20K tokens (seeds 11, 23 and 37 of the [Codex retention corpus](codex_retention_20261005.md)); one session per history and condition; six turns (five questions and a JSON summary).

| Condition | Mean six-turn cost | Single questions correct | JSON summary values correct |
|---|---:|---:|---:|
| Full history, cache active throughout | $0.0197 | 11/15 | 11/15 |
| TOMC once at the start (40% budget), unchanged afterwards | $0.0089 (−55%) | 14/15 | 14/15 |

Turns 2–6 read over 95% of the prompt from cache in both conditions. TOMC still cost less per turn because cached reads are discounted, not free, and its prompt was about half as long. All four full-history errors returned outdated values. Switching to TOMC midway through a warm conversation costs one cache write; in this run that equalled about six warm turns and paid back after about ten.

## Simulation of the automatic request loop

We captured the exact messages `AutomaticChatSession` produced and billed each request by its longest message-level common prefix with an earlier request, assuming every request falls inside the cache lifetime. Prices are relative to the uncached input price: Anthropic-style (write 1.25×, read 0.1×), OpenAI/DeepSeek-style (miss 1×, hit 0.1×) and a 50× cache discount (hit 0.02×). Output is excluded. Forty turns, default 80% memory budget, mean of three histories; input cost relative to sending the full history with caching:

| Policy | Chat (1 request/turn) | Agent loop (2 requests/turn, long tool outputs) | Cache hit rate |
|---|---:|---:|---:|
| Previous default, `refresh_policy="cadence"`, `refresh_every=2` | +538% to +1618% | +622% to +2219% | about 4% |
| New default, `refresh_policy="stable"` | −16% | −12% | 95–97% |

The previous policy used the latest user message as the task, so an ordinary chat rebuilt the memory on almost every request, and the rebuilt memory rarely fit the reuse budget. Rebuilding only when the request no longer fits matters in agent loops: with an 8K growth trigger the stable policy still cost 5–52% more than the full history.

Earlier results are unaffected: the Codex retention and stacking comparisons answered each question in a fresh session, so both conditions were uncached, and the MCP plugin prepares context only when called rather than rewriting a host's requests.

## Limits

One model, three related synthetic histories and one session per condition in the live run. The simulation uses message-level prefix matching and ignores minimum cache sizes, block granularity and expiry, which differ by provider. Reusing memory compiled for an earlier task can omit a detail that a later task needs; check important answers.
