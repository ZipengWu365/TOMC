<div align="center">
  <img src="assets/tomc_logo_20261002.png" alt="TOMC Memory" width="320">
  <h1>TOMC Memory</h1>
  <p><a href="README.md">English</a> | <strong>简体中文</strong> · v0.3.1 研究预览版 · MIT 开源 · Python 3.10+</p>
</div>

每开一个新的 AI 对话，我都要把项目从头讲一遍。讲完它还报给我一个早就改掉的旧方案。我受够了，就做了这个。

**改过的事，只记最新的。**

比如项目框架从 Flask 换成 Django，又换成 FastAPI，最后定了 Litestar。TOMC Memory 交给助手的是 `framework = Litestar`，还附上这句话在第几行。

**装好后对助手说：试一下 TOMC Memory。** 在终端里也可以运行 `tomc try`。

- **离线查旧值（v0.3.0）：** 每种预算 144 道题，每题问一件改过 3 到 5 次的事。默认预算下，准备好的上下文每题都带着最新值（v0.2.1 是 58%）。只留 10% 时是 85%（v0.2.1 是 51%）。用的是合成的笔记和聊天，不调用模型；这套题是和这次修复一起写的，算我们自己的回归测试。
- **Codex 里少发多少（0.1.0 预览版测的，之后没重测）：** 9 份合成项目聊天，每份约 1 万到 4 万 token，每份问 5 题，模型 `gpt-6.1-sol`。只留 40% 的历史，请求输入平均少 29.7%，45 题仍然全对。每种条件只跑一次。
- **BEAM 长历史测评（论文实验）：** 同一个回答模型分别读 TOMC 和另外 6 种记忆方法准备的内容，共 3 个模型。在 50 万到 1000 万 token 的历史上，54 组比较里 TOMC 的平均分都更高；10 万 token 时是 18 组里 17 组。只比平均分，不能和其他项目公布的 BEAM 分数直接比。

[每个数字的来源、条件和没做好的地方](docs/evidence_zh.md) · [使用前须知](#before-you-use-it) · [安装](#install)

<a id="before-you-use-it"></a>

## 使用前须知

1. **它不会让助手当前的对话变短。** Claude Code、Codex 自己管理当前对话。TOMC Memory 只处理你交给它的历史和你存下的笔记。[上下文归属说明](docs/context_ownership_zh.md)
2. **历史短，省得就少。** 不到 1 万 token 时没多少可删的。按默认预算，我们之前的测试大约省 1 到 2 成输入（Codex 9.2%，Claude API 式请求 19.8%，都是 0.1.0 预览版）。预算调小能省更多，但可能丢掉最新值，先拿自己的任务对比一下。默认预算：1 万 token 以内保留 80%，越长留得越少，到 100 万 token 时保留 60%，最少 1,024 token。
3. **它按字面挑内容，不懂换了说法的话。** 像"算了，还是用 Django"这种改口，预算小的时候可能漏掉。如果后面某一行可能改过某个值，这个值会标成 `STATE?`，并附上那一行原文，方便你或助手核对。
4. **会存什么，怎么删。** `prepare_context` 和 `recall_memory` 的结果默认不保存，要保存得自己打开（`tomc settings --save-mcp-results on`）。用 `remember_memory` 存的笔记只放在你自己电脑的 `~/.tomc/memory.sqlite3` 里。删一个笔记本用 `forget_memory`，全部清空用 `tomc erase-all --yes`。[安全与隐私](SECURITY.md)
5. **不是每个客户端都验证过。** Codex 和 Claude Code 在早期预览版上做过真实模型调用。Cursor、TRAE、WorkBuddy 只写好了配置方法，还没在真机上确认工具能被调用。Claude Desktop 也还没在应用里实际装过。
6. **论文还没公开。** 测评数字来自我们自己的实验设置。[证据页](docs/evidence_zh.md)列出了来源、样本量，以及哪些能离线复查（`make reproduce`）。

<a id="install"></a>

## 安装

不管走哪条路，最后都一样：新开一个对话，说 **"试一下 TOMC Memory"**；不对劲就运行 `tomc doctor`。Claude Code 和 Codex 插件需要先装 [uv](https://docs.astral.sh/uv/getting-started/installation/)。从源码运行需要 Python 3.10 或更新版本（先看 `python3 --version`；macOS 自带的 3.9 太旧）。

<a id="claude-code"></a>

### Claude Code

```text
/plugin marketplace add ZipengWu365/TOMC
/plugin install tomc-memory@tomc
```

新开会话，用 `/mcp` 确认有 `plugin:tomc-memory:tomc`，然后说"试一下 TOMC Memory"，或者运行 `/tomc-memory:try`。[Claude Code 详细说明](docs/assistant_plugin_zh.md#claude-code)

<a id="codex"></a>

### Codex

下载 [tomc-memory-codex-0.3.1.zip](https://github.com/ZipengWu365/TOMC/releases/download/v0.3.1-preview.1/tomc-memory-codex-0.3.1.zip)，解压到一个不会删的文件夹，在里面运行：

```bash
uv run --no-project --python 3.12 install.py --check
uv run --no-project --python 3.12 install.py
```

安装器装完会自己启动一次服务做检查。新开 Codex 会话，说"试一下 TOMC Memory"。[Codex 完整步骤](docs/assistant_plugin_zh.md#codex)

<a id="any-mcp-client"></a>

### 其他 MCP 客户端（Cursor、Claude Desktop、WorkBuddy、TRAE 等）

```bash
git clone https://github.com/ZipengWu365/TOMC.git && cd TOMC
python3 -m venv .venv && .venv/bin/python -m pip install -e '.[mcp]'
.venv/bin/tomc setup --client cursor --write   # 也可以是 claude-desktop、claude-code、codex、workbuddy
.venv/bin/tomc doctor
```

`--write` 会先备份客户端的配置文件，原有的其他服务不动。TRAE 或项目级配置文件加上 `--config 配置文件路径`。重启客户端，说"试一下 TOMC Memory"。Windows 上用 `py -3.12 -m venv .venv` 和 `.venv\Scripts\`。[各客户端说明](docs/assistant_plugin_zh.md#setup-write)

<a id="python-api"></a>

### Python API

```python
from tomc import prepare_context  # 在克隆的目录里 pip install -e .，没有第三方依赖

prepared = prepare_context(history, task)
response = client.chat.completions.create(model=model, messages=prepared.messages)
```

用 `prepared.messages` 替换原来的历史；接在原历史后面反而会多花输入。运行 `.venv/bin/tomc try` 可以离线看一个完整例子。[API 说明](docs/api_reference.md)

<a id="mainland-china-network"></a>

### 中国大陆网络

GitHub 或 PyPI 下载卡住时，给 pip 和 uv 换镜像：

```bash
python3 -m pip install --user uv -i https://pypi.tuna.tsinghua.edu.cn/simple
export UV_DEFAULT_INDEX=https://pypi.tuna.tsinghua.edu.cn/simple
export UV_PYTHON_INSTALL_MIRROR=https://registry.npmmirror.com/-/binary/python-build-standalone
python3 -m uv run --no-project --python 3.12 install.py   # Codex 安装器，在解压后的文件夹里运行
```

从源码安装时，在 `pip install` 那行后面加 `-i https://pypi.tuna.tsinghua.edu.cn/simple`。PowerShell 里用 `$env:UV_DEFAULT_INDEX="…"` 设置变量。

## 想了解更多

- [证据与数字台账](docs/evidence_zh.md)：每个数字的来源文件、模型、样本量和版本，以及没做好的结果。
- [0.3.1 更新说明](docs/release_notes_0.3.1_zh.md) · [0.3.0](docs/release_notes_0.3.0_zh.md) · [离线复查](docs/reproducibility.md) · [独立复现记录](REPLICATIONS.md)
- [换助手接着干](docs/usage_tips_zh.md#reuse-notebooks)：在 Codex 里存，到 Claude Code 里取，同一台电脑。
- [桌面小猫（测试版）](docs/desktop_companion.md#chinese-quickstart)：常驻显示今天估算少发了多少，还能生成一张可以分享的[本周战报](docs/share_card_zh.md)，支持 Windows 和 macOS；可选的请求网关只支持 Windows。Linux 只有插件和 MCP 服务。
- [本地 Demo](docs/quickstart.md) · [原理](docs/method.md) · [中文使用技巧](docs/usage_tips_zh.md) · [验证记录](docs/validation.md)
- [视频介绍（1 分 28 秒）](launch/media/v13/videos/TOMC_Overview_ZH.mp4)。视频里有一个 Codex 数字在仓库里找不到测试记录，见[素材说明](launch/media/v13/README.md)。

## 社区、引用与许可

<!-- community-entry:start -->
**试用、评测与参与：** [首次使用反馈（中英文）](https://github.com/ZipengWu365/TOMC/issues/11) · [上下文压缩评测笔记](https://github.com/ZipengWu365/ZipengWu365/blob/main/notes/2026-10-27-context-compression-checklist.zh.md) · [贡献指南](CONTRIBUTING.md)

关注 [Zipeng Wu](https://github.com/ZipengWu365)，了解时间序列研究软件与 AI 任务记忆的后续工作。Star 用于收藏 TOMC；项目通知可通过 Watch 设置。关注和 Star 都是自愿的，不影响获得帮助。
<!-- community-entry:end -->

<p><a href="https://github.com/ZipengWu365/TOMC/stargazers"><img src="assets/traffic/stars.svg" alt="GitHub Stars" height="20"></a> <a href="docs/traffic_metrics.md"><img src="assets/traffic/clones-total.svg" alt="Cumulative recorded clones" height="20"></a></p>
<!-- traffic-status:start -->
  <p>累计克隆 · 自 2026-10-02 起记录 · 更新于 2026-11-07 UTC。 <a href="docs/traffic_metrics.md">统计口径与更新</a></p>
<!-- traffic-status:end -->

MIT 许可：可以免费使用、修改、分发，包括商用，保留版权和许可声明即可。如果 TOMC Memory 对你的研究有帮助，请用 [CITATION.cff](CITATION.cff) 引用（GitHub 页面上的 "Cite this repository"）。示例都是合成数据；仓库只放测评的汇总数字，不含题目原文、回答和 API 请求内容。[数据来源](DATA_PROVENANCE.md) · [数据与许可](docs/data_and_license.md)
