# GitHub 首页与图组：第二轮改进

2026-09-09。目的：回应作者对 LLMLingua GitHub 主页与配图风格的偏好。范围是 README、原创标识、解释图和研究结果图；传播效果仍待真人验证。

本稿记录早期视觉研究。当前首页以提交论文的方法图和结果图为准；具体对应关系见 [论文定位核对](../docs/paper_scope.md)。

## 看了哪些原图

直接检查了[官方 README](https://github.com/microsoft/LLMLingua)、[问题动机图](https://github.com/microsoft/LLMLingua/blob/main/images/LLMLingua_motivation.png)、[总览图](https://github.com/microsoft/LLMLingua/blob/main/images/motivation.png)、[LLMLingua 方法图](https://github.com/microsoft/LLMLingua/blob/main/images/LLMLingua.png)和[LLMLingua-2 方法图](https://github.com/microsoft/LLMLingua/blob/main/images/LLMLingua-2.png)。观察到的视觉特征是白底、较深的轮廓、浅色功能分区、箭头与图标、少量关键词强调；图文沿着动机、机制、结果展开。这里借鉴视觉表达方式，不据此推断 star 或转化增长的原因。

## 对上一轮的再反思

上一轮的米白/墨绿界面适合交互工作台，但 README 仍像把界面卡片搬进文档。单一快照图说明了一个行为，却没有先解释任务、记忆表示、预算与来源之间的关系。研究图只有左侧效应区间，输入减少要回到表格查。品牌标识也没有独立于标题形成记忆点。

本轮把论文项目首页分成三个层次：**总览图回答“它是什么” → 机制图回答“如何工作” → 结果图回答“证据支持到哪里”**。每张图都配有可以独立阅读的说明，不要求读者先看完论文。

## 已实现的设计

| 部分 | 处理 | 原因 |
|---|---|---|
| 页首 | 原创 TOMC 状态卡片标识、居中标题、精简导航与运行条件 | 让项目身份和试用入口先被看到 |
| 总览图 | 蓝色历史、绿色编译/状态、独立来源检查区；按论文展示任务相关记录与原文证据，再交给大模型 | STATE / RELATION / COUNT / RAW 是主论文的路由 |
| 快照图 | 赋值 → COPY → 更新，来源 ID 与实际输出一致 | 直观解释“旧副本与新状态并存”，不冒充自然语言推理结果 |
| 结果图 | Full-grid 效应区间与 reader 输入减少并排 | 同时回答效果、输入开销和不确定性 |
| 移动端 | 中英文机制图另有纵向版本，通过 picture/source 切换 | 不把整张横向论文图缩成难读的小字 |
| 深色模式 | 图本身保留白底和深色文字 | 防止透明底导致文字融入 GitHub 深色背景 |

状态与编译用绿色，历史与原文用蓝色，快照副本用琥珀色。关键角色还通过标题与文字表达，避免只靠颜色。图片源文件是可编辑 SVG；统计图由标准绘图库生成，相关数值与源哈希写入 `assets/figure_data.json`。

## 保留的证据约束

1. 合成快照例子真实运行后是 31 → 36 个估算 token；来源元数据使短输入变长，图中明确说明。
2. 图中只展示部分操作/输出行时，在图注中标明；完整例子还包含 seat。
3. BEAM 图使用 full-grid 效应和对应区间，表格使用 available-pair 得分；两种点估计略有差异，图注解释其口径。
4. Flash 保留非显著标记，缺失扩展区间不删除；负结果和 Demo/冻结适配器差异继续展示。
5. 原创图组不加入未经实现的框架 logo、虚构模型回答、机构背书或未发布的论文/PyPI 徽章。

## 下一轮最值得验证什么

按[私测任务卡](PILOT_ZH.md)，先看用户能否在无提示下理解这是大模型的任务相关记忆、完成上下文交接、解释快照并找到证据。如果总览看懂但导入自己的历史仍困难，下一轮优先做输入适配与示例，而不是继续增加装饰。短视频仍需实际录制；本轮交付的是图组和首页，不把静态图片记作视频完成。

官方支持在 Markdown 中使用 [`picture` 元素](https://docs.github.com/en/get-started/writing-on-github/getting-started-with-writing-and-formatting-on-github/basic-writing-and-formatting-syntax)。实际页面的窄屏选择和图片链接另经渲染检查；其他 Markdown 查看器可以使用默认横图，并单独打开纵图。
