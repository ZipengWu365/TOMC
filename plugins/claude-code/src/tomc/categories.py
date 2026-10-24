"""Common kinds of work, used to describe conversations without naming them.

Classification runs locally on a conversation's own name, folder and saved task
lines. Only the category code ever leaves the computer, and only in a feedback
report the user reviews and submits.
"""

from __future__ import annotations

import re

# code, Chinese label, English label, comma-separated keywords (case-insensitive).
_TABLE = (
    (
        "coding",
        "编程开发",
        "Coding",
        "code, coding, bug, debug, fix, test, pytest, api, sdk, gateway, python, javascript, "
        "typescript, rust, golang, java, kotlin, swift, git, commit, branch, merge, "
        "pull request, repo, deploy, build, compile, refactor, plugin, script, backend, "
        "frontend, server, sql, database, docker, kubernetes, linux, shell, install, ci, lint, "
        "编程, 代码, 报错, 修复, 部署, 接口, 函数, 脚本, 插件, 编译, 前端, 后端, 数据库, "
        "安装, 重构, 测试, 开发, 网关, 仓库",
    ),
    (
        "paper",
        "论文与学术",
        "Papers & research writing",
        "paper, arxiv, latex, tex, neurips, icml, acl, cvpr, appendix, abstract, "
        "rebuttal, reviewer, citation, manuscript, experiment, benchmark, ablation, theorem, "
        "proof, thesis, 论文, 附录, 摘要, 审稿, 引用, 实验, 投稿, 学位, 定理, 证明",
    ),
    (
        "writing",
        "写作与文案",
        "Writing & copy",
        "write, writing, draft, article, blog, essay, copy, translate, translation, email, "
        "letter, proofread, rewrite, newsletter, docs, documentation, readme, "
        "写作, 文案, 文章, 博客, 翻译, 邮件, 润色, 改写, 稿, 文档, 说明",
    ),
    (
        "video",
        "视频与多媒体",
        "Video & media",
        "video, clip, edit video, subtitle, caption, voiceover, audio, podcast, youtube, "
        "bilibili, tiktok, douyin, capcut, premiere, "
        "视频, 剪辑, 字幕, 配音, 音频, 抖音, 剪映, 动画, 分镜, 录屏",
    ),
    (
        "design",
        "设计与图像",
        "Design & images",
        "design, figma, ui, ux, logo, icon, poster, figure, image, illustration, layout, "
        "mockup, palette, 设计, 界面, 海报, 图标, 配图, 插画, 排版, 配色",
    ),
    (
        "data",
        "数据分析",
        "Data & analysis",
        "data, analysis, analytics, dashboard, chart, excel, csv, spreadsheet, pandas, "
        "statistics, metrics, 数据, 分析, 统计, 表格, 图表, 看板, 报表",
    ),
    (
        "marketing",
        "运营与社媒",
        "Marketing & social",
        "marketing, promotion, social, twitter, linkedin, xiaohongshu, seo, campaign, launch, "
        "followers, reply, comment, 宣传, 推广, 运营, 小红书, 社媒, 评论, 回复, 粉丝, 营销",
    ),
    (
        "learning",
        "学习与调研",
        "Learning & research",
        "learn, study, research, survey, explain, tutorial, summary, summarize, notes, course, "
        "学习, 调研, 研究, 解释, 教程, 总结, 笔记, 阅读, 课程, 了解",
    ),
    ("other", "其他", "Other", ""),
)
CATEGORIES = tuple(
    (code, zh, en, tuple(word.strip() for word in words.split(",") if word.strip()))
    for code, zh, en, words in _TABLE
)
CODES = tuple(code for code, *_ in CATEGORIES)
_LABELS = {code: (zh, en) for code, zh, en, _ in CATEGORIES}
_ASCII = re.compile(r"[a-z0-9 ]+")


def label(code, language="zh"):
    zh, en = _LABELS.get(code, _LABELS["other"])
    return en if getattr(language, "code", language) == "en" else zh


def _hits(text, keyword):
    if _ASCII.fullmatch(keyword):
        # Whole words only, so "ci" does not match "social" and "tex" not "context".
        return len(re.findall(rf"(?<![a-z0-9]){re.escape(keyword)}(?![a-z0-9])", text))
    return text.count(keyword)


def classify(*texts):
    """The best-matching category for these local texts; "other" when nothing matches.

    The first text (the conversation's own name) counts double. Ties keep the
    order of ``CATEGORIES``.
    """
    scores = dict.fromkeys(CODES, 0.0)
    for position, text in enumerate(texts):
        if not isinstance(text, str) or not text.strip():
            continue
        text = text.casefold()
        weight = 2.0 if position == 0 else 1.0
        for code, _zh, _en, keywords in CATEGORIES:
            scores[code] += weight * sum(_hits(text, keyword) for keyword in keywords)
    best = max(CODES, key=lambda code: (scores[code], -CODES.index(code)))
    return best if scores[best] > 0 else "other"
