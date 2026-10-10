# Hugging Face deployment settings

The GitHub homepage is `README.md`. Space configuration is kept here so GitHub does not render it as a large table above the product introduction. The running Space retains its existing configuration.

Hugging Face requires these settings as YAML front matter at the **start of the Space's root `README.md`**. They cannot be moved to the end of that file. The staging command copies the verified release files, prepends this block to the GitHub README, and generates checksums for the resulting Space files. It leaves the GitHub README and release inventory intact.

```bash
python scripts/stage_hf.py --repo-id Zipeng365/tomc-agent-memory-demo
```

Do not upload the unmodified GitHub README as the Space README.

```yaml
---
title: TOMC Memory Workbench
emoji: 🗂️
colorFrom: green
colorTo: gray
sdk: gradio
sdk_version: 5.49.1
python_version: '3.10'
app_file: app.py
fullWidth: true
license: mit
short_description: CPU memory for your existing LLM API.
tags: [llm-memory, long-context, context-compression, reproducibility]
---
```

The private Space is [Zipeng365/tomc-agent-memory-demo](https://huggingface.co/spaces/Zipeng365/tomc-agent-memory-demo). These settings preserve its SDK, Python version and entry point. They do not change access or hardware.
