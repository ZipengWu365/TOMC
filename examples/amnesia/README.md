# AI 失忆现场 / AI amnesia stories

这里放的是从投稿改写来的**合成**例子：一件事在长对话里改过几次，看 TOMC Memory 能不能把最新的那个值带回来。

These are **synthetic** cases rewritten from people's stories: a fact changed a few times in a long chat, and the test checks that TOMC Memory brings back the latest value.

## 从故事到测试 / From a story to a test

1. 有人在 Discussions 的 "AI amnesia stories / AI 失忆现场" 分类（或 `AI 失忆现场` issue 表单）里讲了经过。
   Someone posts what happened in the "AI amnesia stories / AI 失忆现场" discussion category, or with the issue form.
2. 维护者用**假的值**把它改写成一段历史，存成 `examples/amnesia/<id>.txt`。原文、名字、公司、路径都不进仓库。
   A maintainer rewrites it with **made-up values** as `examples/amnesia/<id>.txt`. The original text, names, companies and paths never enter the repository.
3. `tests/test_amnesia_examples.py` 会自动跑每个文件：用很紧的预算（`budget`）调用 `prepare_context`，检查整理后的状态行里只剩最新值，旧值不会被当成当前值。
   `tests/test_amnesia_examples.py` runs every file: it calls `prepare_context` with a tight `budget` and checks that the compiled state lines hold the latest value and no old value is presented as current.

文件格式 / File format:

```text
# id: seed-001                      文件名去掉 .txt / file name without .txt
# title: 一句话说明 / one-line summary
# status: 用户自述，未复现 / reported, not reproduced
#     或 / or: 已复现（附命令） / reproduced
# command: 复现命令（已复现时必填）/ command that reproduces it (required when reproduced)
# credit: 署名或 anonymous / credit name or anonymous
# task: 最后问 AI 的问题 / the question asked at the end
# key: 状态行的名字，例如 api_base / the state-line key, e.g. api_base
# latest: 最新的值 / the latest value
# stale: 旧值1, 旧值2 / old values, comma-separated
# budget: 200
---
历史，一行一条消息 / the history, one message per line
```

`assistant`、`fact`、`changes` 这几行可以照抄投稿表单里的选项，测试不读它们。
The `assistant`, `fact` and `changes` lines may copy the form answers; the test does not read them.

## 两种标记 / Two labels

每个例子都要标一种 / Every case carries one of:

- **用户自述，未复现 / reported, not reproduced**：我们只有投稿人的描述，没有在原来的助手里重现过。
  We only have the reporter's account; nobody re-ran it in the original assistant.
- **已复现（附命令） / reproduced**：`command` 一行写明怎么重现。
  The `command` line says how to reproduce it.

## 署名 / Credit

- 用投稿人在表单里写的署名；写 "匿名" 或 "anonymous" 就不署名。
  We use the credit name from the form; "匿名" or "anonymous" means no name.
- 署名写在例子文件的 `credit` 行，也会写进对应的提交说明。
  The credit goes on the case's `credit` line and in the commit message that adds it.
- 只有勾了"可以改写成合成例子"的投稿才会被改写。
  Only stories whose authors ticked "OK to rewrite as a synthetic test case" are used.

## 这些故事不能说明什么 / What these stories cannot show

投稿是自愿的，讲出来的多半是印象深的失败，样本是自己挑出来的。所以**不要**用它们算"X% 的 AI 会失忆"或者比较哪个助手更好。它们只用来做回归测试：确认同类情况 TOMC Memory 不会退步。

Stories are volunteered, and people tend to share the memorable failures, so the sample is self-selected. **Do not** use them to compute "X% of AIs forget" or to rank assistants. They are regression tests only: the same kind of case must not get worse in TOMC Memory.

## 现有例子 / Cases

| id | 说明 / summary | 状态 / status | 署名 / credit |
| --- | --- | --- | --- |
| [seed-001](seed-001.txt) | 接口地址在一段长对话里改了三次 / the API address changed three times | 已复现（附命令） / reproduced | 维护者写的种子例子，不是投稿 / maintainers' seed, not a user story |

跑一遍 / Run them:

```bash
python -m pytest tests/test_amnesia_examples.py
```
