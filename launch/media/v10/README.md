# TOMC · 30-second demo · v10

The ending explains how the tested models use TOMC: API models receive prepared context; native coding agents call TOMC tools. Model names follow the author's October 10, 2026 test list. [Test-list provenance](evidence/tested_models_v10.json).

| Language | Landscape | Portrait |
| --- | --- | --- |
| English | [MP4](videos/TOMC_CodeAgent_Complete_EN.mp4) | [MP4](videos_vertical/TOMC_CodeAgent_Complete_EN_9x16.mp4) |
| 中文 | [MP4](videos/TOMC_CodeAgent_Complete_ZH.mp4) | [MP4](videos_vertical/TOMC_CodeAgent_Complete_ZH_9x16.mp4) |

Each video is 30 seconds at 30 fps, with H.264 video and AAC audio. Landscape is 1920 × 1080; portrait is 1080 × 1920. GIF previews, cover images and subtitles accompany the films. The final screen remains 3 seconds. [Media checks](evidence/complete_v10_media_check.json).

**Recorded demo measurements:** Windows Codex input 38,786 → 27,235 tokens, with 5/5 latest-state answers retained; Claude Code recorded session cost US$0.400 → US$0.249, with 5/5 latest-state answers retained. These are separate synthetic task trials with separate protocols, not a five-model benchmark or a general savings guarantee. [Windows Codex protocol](../../../docs/codex_retention_20261005.md) · [Validation record](../../../docs/validation.md).

The flow illustrates explicit save/recall of TOMC project notes. Same-device continuation and manual Git transfer to another device each allow either the same assistant or a different assistant. Native chat histories and permissions are not transferred; Git transfer is manual.

## 中文说明

结尾列出五个已测模型，并说明用途：DeepSeek 4.1 Flash、DeepSeek 4 PRO 和小红书 Red preview 使用 TOMC 准备的上下文；Claude 5.5 Opus 与 ChatGPT Codex 6.1 Sol 在代码助手中调用 TOMC 工具。DeepSeek 4 PRO 的测试由作者确认，本次素材编辑没有新增模型评测。各模型不共享同一测试协议。

TOMC 目前是研究预览。欢迎试用、反馈、提交 Issue/PR，以及交流与研究合作。

The repository remains a private preview as of this update. Its [current license](../../../LICENSE) is PolyForm Noncommercial 1.0.0. The welcome message does not change that license. Model-service fees still apply; provider logos do not imply endorsement. License and public-release choices are being discussed separately.

