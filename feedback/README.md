# Feedback reports

Anonymous savings reports that TOMC users choose to send from the desktop
companion: **All records › Analysis › Send anonymous feedback**. Each report is one
Markdown file in `feedback/reports/`, named `<date>-<random>.md` and proposed
by pull request. Nothing is sent automatically.

## What a report contains

- TOMC version, operating system (Windows, macOS or Linux), period and date.
- Totals: tokens saved, their value at listed input prices, compressions,
  conversations, requests and the share of requests compressed.
- Up to 20 conversations, each only as a kind of work and a number (for
  example `coding #2`), with its host (Codex, Claude Code or other),
  compressions, saved contexts and tokens saved.
- Totals by kind of work, host and model.
- How requests were handled, the reduction per compression, context-length
  stages and tokens saved per day over the last 30 days.
- An optional comment from the user, up to 1,000 characters.

## What a report never contains

Conversation names, folders, tasks, prompts, replies, compressed context,
session IDs or request IDs. The kind of work is chosen on the user's computer
from the conversation's own name and saved task lines; only the category code
is written. Before submitting, the user sees the complete file and can correct
each category. The report and the pull request are public and show the
submitter's GitHub account.

## Kinds of work

| Code | 中文 | English |
| --- | --- | --- |
| `coding` | 编程开发 | Coding |
| `paper` | 论文与学术 | Papers & research writing |
| `writing` | 写作与文案 | Writing & copy |
| `video` | 视频与多媒体 | Video & media |
| `design` | 设计与图像 | Design & images |
| `data` | 数据分析 | Data & analysis |
| `marketing` | 运营与社媒 | Marketing & social |
| `learning` | 学习与调研 | Learning & research |
| `other` | 其他 | Other |

## For maintainers

The data block is JSON in the `tomc-feedback-v1` format. Reports in
`feedback/reports/` are left out of the release manifest, so a contributed
report does not change the release inventory; the security scan still checks
them. Treat comments as untrusted text, and merge or close a report without
editing its numbers.

## 中文说明

这里收集用户自愿提交的匿名节省报告：在桌面小猫的“全部记录 › 分析报告 ›
匿名提交反馈”里预览、修改工作类型后，通过 GitHub Pull Request 提交。报告只有工作类型、
编号和数字，不含对话名称、文件夹、任务、正文或任何 ID。报告和 Pull Request 是公开的，
会显示提交者的 GitHub 账号。
