# TOMC 当前桌面小猫

2026-10-18 21:31 UTC 已更新本机入口、官方费率同步与绿洲故事。这份状态覆盖此前旧价格与旧绿洲时长记录。

- 当前安装目录：`%USERPROFILE%/.codex/tomc/pet-current`，以 `CURRENT.json` 的时间和资产校验值为准。
- 唯一启动入口：`%USERPROFILE%/.codex/tomc/pet.pyw`。桌面快捷方式为 **TOMC**。
- `pocket.pyw`、`hourglass.pyw` 现为兼容转发入口；启动它们不会回到旧猫。重复启动被单实例锁拦截。
- assistant-preview.4、assistant-preview.5、旧 hourglass-0.1.2 安装目录和 Codex 插件缓存中的 UI 模块入口均已转到当前入口。MCP 后端配置没有改变。
- 最新四阶段都只有猫头、同名 TOMC，平时委屈丧脸，处理时微笑。小尺寸 72、动画时 132 逻辑像素。配置定价后主统计为“预计少花”美元，token 与百分比在详情；Claude 额度尚未接入。
- 定价配置 `~/.tomc/pricing.json` 当前参考 Claude Code 最近活动会话模型 `claude-opus-5-5`，未缓存标准输入 $4/百万 tokens。识别证据与假设均可查看；这不是对下一次调用模型的保证。Codex 默认配置检测为 `gpt-6-astra`；Cursor 尚未接入逐请求模型记录，Auto 不猜测。
- 每次运行 `scripts/install_current_pet.py` 都同步 OpenAI、Anthropic、DeepSeek、Cursor 官方费率，并更新 `~/.tomc/detected_models.json`。费率缓存在 `~/.tomc/prices.json`，含来源、核验 UTC 时间、校验值和失败状态。断网或解析变化保留旧费率/原日期，不伪装更新成功。手动选定的参考模型不会被安装覆盖。
- 小面板为 240 像素宽；点击「估价」或右键「模型与估价」可查看各模型/服务档位/缓存费率与当前范围的美元折算，切换参考模型。包括 OpenAI 短/长上下文与 Standard/Batch/Flex/Fast、Claude 基础价与 Haiku 长上下文、DeepSeek 峰谷价、Cursor 公布模型基础价。Cursor 套餐、团队附加费、旧版 Max 加价和地区溢价未纳入；不等于完整 Cursor 账单。
- 累计是全部准备记录按当前选择的单价折算，不是历史每次模型的实付合计。词法估算未确认文本真正发送，不含输出/工具/额外请求开销，重复准备分别累计；缓存改变可能抵消收益。模型/费率未知显示「费率待确认」，订阅月费和额度节省不由此推算。
- 首次进入皇冠阶段会播放约 10.5 秒的沙漠变绿洲、树木花草、兔子与鸟群动画；画面中皇冠猫微笑。四段字幕讲减少重复输入、可能降低计算和用电、可能减少冷却用水压力、资源留给自然。右键「绿洲的故事」可读完整逻辑和研究来源。随后普通皇冠调用不重复触发，可右键重播。虚拟成长不代表实际植树、节水或节电，没有捏造升数。
- `pet.pyw --demo` 播放四段动画。演示数字写在独立的 `~/.codex/tomc/pet-demos/` 时间戳目录，不写真实统计库；关闭演示后恢复真实统计猫。
- 正常运行读取 `%USERPROFILE%/.tomc/memory.sqlite3`。只使用 Qt 自身渲染，不使用桌面控制/截图。
- `outputs/pet_final_path.txt`、`cat_release_path.txt`、`cat_demo_path.txt` 已统一指向当前安装目录。旧素材和输出目录仅作历史存档，不代表当前版本。

原入口备份位于 `~/.codex/tomc/archive/pet-entrypoints-*`。没有更改论文、发布远程版本或改写用户历史统计。

验证：17 项定价/统计/额度单元测试通过；Qt 自身组件验证模型切换、缓存、未知模型、小面板宽度、首次皇冠/自动收起/点击收起；四阶段动画检查通过。记录在 `outputs/pricing_sync_20261018/`。未使用桌面控制或截取其他应用。
