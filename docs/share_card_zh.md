# 本周战报

[English](share_card.md)

TOMC Memory 可以把最近 7 天画成一张图：少发给模型多少 token、7 天柱状图，再加几格小数据。图在你自己电脑上生成，不会上传。发不发由你决定。

## 怎么生成

在小猫、看板或分析页里点 **本周战报**，会先出预览：

- **隐藏金额**：去掉金额那一行，连带去掉按哪个模型标价算的。
- **横版**：从 1080×1350（4:5，适合 B 站动态和小红书）换成 1200×630。
- **复制图片** 放进剪贴板；**保存 PNG…** 默认存到"图片"（没有就存桌面），文件名 `TOMC-本周战报-YYYYMMDD.png`。

在终端里（没有屏幕也能用）：

```bash
tomc share-card                      # 存到当前文件夹，语言跟终端
tomc share-card --lang zh --landscape --out ~/Pictures
tomc share-card --hide-money --out card.png
```

会打印文件路径和一句话总结。需要 PySide6：`pip install 'tomc-memory[widget]'`。

## 数字是什么意思

- **少发了多少 tokens**：最近 7 个 UTC 日里，TOMC Memory 整理前后上下文文本的差。token 是本机文本估算（卡上写了用的哪种计数），不是模型那边的计数。
- **占比**：少发的量除以原本要发的量。可用记录少于 5 次时，卡上只写"样本太少"，不给百分比。
- **金额**：写成"按标价估算 ≈ $x"，等于少发的量乘以卡上那个模型的未缓存输入（或缓存读取）标价。这不是账单；有缓存或订阅时实际差得更少。不知道标价就不显示金额，不会写 $0。
- **压缩覆盖**：用 Windows 网关测试版时是"18 个请求里压缩了 12 个"；用 TOMC 工具调用时是"几次整理里几次变短"。
- **最省的工作类型**：来自网关的请求记录，只写工作类型。

## 卡片一定遵守的规则

- 每个 token、金额、百分比旁边都有"≈"或"估算"。
- 页脚固定写"上下文估算，不等于账单或额度节省"和 token 的计数方式；显示金额时还写按哪个模型标价估算。这几行关不掉。
- TOMC 工具调用和 Windows 网关测试版的口径不同，分开列，不相加。
- 这周没省到就写"本周没省到"；上下文变长了也照实写。
- 演示或测试数据会斜着铺满"演示数据 · DEMO DATA"水印，关不掉。
- 不把省下的 token 换算成水、电或树，这些没测过。
- 卡上不出现对话名、文件夹、提示词或任何 ID，只有工作类型。

## 给开发者

```python
from tomc.share_card import card_data, card_strings, summary_line
from tomc.share_card_qt import render_card, show_share_card

data = card_data(path, "zh")  # 只取数和文案，不用 Qt
image = render_card(data, "portrait")  # QImage；"landscape" 是 1200x630
show_share_card(parent, path)  # 预览对话框（不阻塞）
```

`card_strings(data)` 列出卡上画的每一句话，测试用它检查上面这些规则。
