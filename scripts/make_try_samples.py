"""Write the synthetic samples used by `tomc try` and the try_tomc MCP tool.

A 120-day project chat with four framework changes, a backup copy relation and a
production database decision. Deterministic; rerun after editing the text below:

    python scripts/make_try_samples.py
"""

import json
import random
from pathlib import Path

OUT = Path(__file__).resolve().parents[1] / "src" / "tomc" / "data"

EN = {
    "topics": [
        "CI was flaky again on the payment tests; we reran it twice",
        "we went through the onboarding doc and fixed three broken links",
        "long thread about the logging format, JSON or plain lines",
        "the dashboard colours were hard to read on the projector",
        "we bumped two dependencies and the lockfile changed",
        "code review backlog is at 14 pull requests",
        "naming discussion: orders or purchases in the public API",
        "error messages should say what the user can do next",
        "retro: standups run long, try 10 minutes",
        "the staging deploy took 20 minutes, mostly image builds",
        "we drafted release notes for the next minor version",
        "on-call handoff notes were missing the alert links",
        "accessibility check on the checkout form found two labels missing",
        "the nightly benchmark moved by 3 percent, probably noise",
        "translation of the help pages is half done",
    ],
    "replies": [
        "Noted. I listed three follow-ups for the team; nothing changes in the plan this week.",
        "Summarised for the team channel with links. No decision is needed today.",
        "Added to the backlog with an owner and a due date, next to the related tickets.",
        "Agreed. I will check it again on Friday and report back in the weekly notes.",
        "Logged in the meeting notes; the plan and the release date stay the same.",
        "OK. I opened a ticket, linked the earlier discussion and pinged the owner.",
    ],
    "followups": [
        "can someone own the flaky test list this week",
        "please keep the meeting notes in the shared folder",
        "the design review moves to Thursday afternoon",
        "remember to tag the release candidate after the merge",
        "the support team asked for a short changelog",
        "we still need a volunteer for the docs sprint",
        "let's not touch the deployment scripts before the demo",
    ],
    "followup": "[user] Also, {text}.",
    "every": 1,
    "user": "[user] Day {day}, morning sync: {text}.",
    "assistant": "[assistant] {text}",
    "events": {
        1: [
            "[user] Day 1: kickoff for the orders service. We start on Flask because the team knows it.",
            "framework = Flask",
        ],
        11: [
            "[user] Day 11: Flask is slowing us down on admin and auth, so we move the main service to Django.",
            "framework = Django",
        ],
        31: [
            "[user] Day 31: the backup service must use the same framework as the main service today.",
            "backup_framework copies framework",
        ],
        61: [
            "[user] Day 61: Django is too heavy for the async workers; the main service moves to FastAPI. The backup service stays as it is.",
            "framework = FastAPI",
        ],
        81: [
            "[user] Day 81: decision on the production database: Postgres, not MySQL.",
            "db = postgres",
        ],
        101: [
            "[user] Day 101: the benchmarks favour Litestar, so we migrate the main service again.",
            "framework = Litestar",
        ],
        111: [
            "[user] Day 111: unit tests use SQLite only; the production database stays Postgres."
        ],
    },
    "title": "built-in sample (120-day project chat)",
    # Both languages use the same stated budget, shown on the card, so the two trials
    # compare like with like; the default budget keeps more (see `tomc prepare`).
    "budget": 200,
    "question": "What are the current framework, backup_framework and production db?",
}

ZH = {
    "topics": [
        "支付相关的 CI 又不稳定，重跑了两次才过",
        "过了一遍新人上手文档，修了三个失效链接",
        "讨论日志格式，到底用 JSON 还是纯文本行",
        "投影上看不清看板的配色",
        "升级了两个依赖，锁文件跟着变了",
        "待评审的合并请求积压到 14 个",
        "对外接口叫 orders 还是 purchases，讨论了很久",
        "报错信息要告诉用户下一步能做什么",
        "复盘：站会太长，试试控制在 10 分钟",
        "预发环境部署花了 20 分钟，主要卡在镜像构建",
        "起草了下个小版本的发布说明",
        "值班交接记录里漏了告警链接",
        "结账表单做了无障碍检查，发现缺两个标签",
        "夜间性能测试波动了 3%，大概是噪声",
        "帮助页面翻译完成了一半",
    ],
    "replies": [
        "好的，列了三个后续事项，计划不变。",
        "已在团队群里总结，今天不用做决定。",
        "已加入待办，写明了负责人和截止日期。",
        "同意，周五我再看一遍，结果同步给大家。",
        "已记进会议纪要，计划保持不变。",
        "好的，开了工单，并附上之前的讨论链接。",
    ],
    "followups": [
        "这周谁来认领不稳定测试清单",
        "会议纪要请放到共享文件夹",
        "设计评审改到周四下午",
        "合并后记得给候选版本打标签",
        "客服希望要一份简短的更新说明",
        "文档冲刺还缺一个志愿者",
        "演示之前先别动部署脚本",
    ],
    "followup": "[用户] 另外，{text}。",
    "every": 3,
    "user": "[用户] 第 {day} 天：{text}。",
    "assistant": "[助手] {text}",
    "events": {
        1: ["[用户] 第 1 天：订单服务启动。团队熟悉 Flask，先用 Flask。", "framework = Flask"],
        11: [
            "[用户] 第 11 天：Flask 在后台管理和登录上拖慢进度，主服务改用 Django。",
            "framework = Django",
        ],
        31: [
            "[用户] 第 31 天：备份服务要和主服务当前用的框架保持一致。",
            "backup_framework copies framework",
        ],
        61: [
            "[用户] 第 61 天：Django 跑异步任务太重，主服务改成 FastAPI。备份服务保持不动。",
            "framework = FastAPI",
        ],
        81: ["[用户] 第 81 天：生产数据库定了：用 Postgres，不用 MySQL。", "db = postgres"],
        101: ["[用户] 第 101 天：性能测试 Litestar 更好，主服务再迁一次。", "framework = Litestar"],
        111: ["[用户] 第 111 天：单元测试只用 SQLite，生产数据库仍然是 Postgres。"],
    },
    "title": "内置样例（120 天项目聊天）",
    "budget": 200,
    "question": "当前的 framework、backup_framework 和生产 db 分别是什么？",
}


def build(spec, seed):
    rnd = random.Random(seed)
    lines = []
    for day in range(1, 121):
        if day in spec["events"]:
            lines.extend(spec["events"][day])
            continue
        lines.append(spec["user"].format(day=day, text=rnd.choice(spec["topics"])))
        lines.append(spec["assistant"].format(text=rnd.choice(spec["replies"])))
        if day % spec["every"] == 0:
            lines.append(spec["followup"].format(text=rnd.choice(spec["followups"])))
    return lines


for lang, spec in (("en", EN), ("zh", ZH)):
    data = {
        "description": "Synthetic sample for `tomc try` and the try_tomc tool. Not real user data.",
        "language": lang,
        "title": spec["title"],
        "question": spec["question"],
        "budget": spec["budget"],
        "lines": build(spec, 7),
    }
    (OUT / f"try_sample_{lang}.json").write_text(
        json.dumps(data, ensure_ascii=False, indent=1) + "\n", encoding="utf-8"
    )
