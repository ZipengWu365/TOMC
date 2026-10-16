# Repository traffic and Stars

The project homepage shows GitHub Stars alongside clone activity. Stars describe voluntary interest; clone activity describes retrieval of the repository. Neither establishes successful installation, retention, software quality or task performance.

| Metric | Definition |
|---|---|
| Stars | Current count supplied by the existing Shields.io GitHub badge |
| Clones, 14-day snapshot | GitHub's count of full clones during the rolling reporting window; fetches are excluded |
| Unique cloners, 14-day snapshot | The window-level `uniques` value returned by GitHub; not a verified count of people or active users |
| Traffic snapshot date | Collection date in UTC, or the date an owner-provided screenshot was recorded |

Automation, repeat setup and maintainer activity can contribute to clone traffic. A clone does not establish that TOMC was installed or used. Daily unique counts are not added to produce the window total. Overlapping 14-day totals are never added to produce a lifetime count.

## Initial snapshot

The initial values were transcribed from the owner's GitHub Traffic screenshot shared on **2026-10-16**: **648 clones** and **194 unique cloners**. The chart displays **2026-10-02 through 2026-10-15**. This is a dated manual snapshot, not a successful API collection. No daily values have been inferred from the plotted lines.

After API collection is enabled, the badges and homepage caption update from the API. The source and timestamp are saved in [`latest.json`](https://github.com/ZipengWu365/TOMC/blob/main/metrics/traffic/latest.json). Dated aggregates are retained in [`snapshots`](https://github.com/ZipengWu365/TOMC/tree/main/metrics/traffic/snapshots). No IP addresses, account lists, notebook content or client telemetry are collected.

## Enable automatic collection

GitHub's [Traffic API](https://docs.github.com/en/rest/metrics/traffic#get-repository-clones) requires repository **Administration: read** for a fine-grained personal access token. The default Actions token does not provide that permission.

1. Create a [fine-grained token](https://github.com/settings/personal-access-tokens/new) with resource owner `ZipengWu365`, repository access limited to **TOMC**, and repository **Administration: Read-only**. Keep the automatically required metadata permission. This token does not need code-write permission. Choose an expiry and renew before it expires.
2. In [TOMC → Settings → Secrets and variables → Actions](https://github.com/ZipengWu365/TOMC/settings/secrets/actions), add repository secret **`TRAFFIC_TOKEN`**. Paste the token there, never into a README, issue or chat.
3. Open [Actions → Update clone traffic badges](https://github.com/ZipengWu365/TOMC/actions/workflows/traffic.yml) and select **Run workflow** on `main`.
4. Check that the collection step reports a successful collection and that the homepage source changes from `owner screenshot` to `GitHub API`.

The workflow is scheduled daily at **06:23 UTC**; scheduled runs can be delayed. It uses the read-only secret only for the Traffic request. GitHub's separate built-in Actions token commits the aggregate data, SVG badges, dated captions and updated release hashes to `main`. Branch rules must allow that write. A conflicting push fails rather than overwriting another change; rerun the workflow after such a failure.

When the secret is missing, the workflow warns and retains the dated snapshot. Expired credentials, HTTP errors or malformed responses do not replace the saved counts with zero. A green workflow that says collection is not configured is not proof of a live refresh. The snapshot date remains visible so stale data is identifiable.

## 中文说明

首页并列展示 Star、最近 14 天克隆次数和独立克隆者，并标明快照日期。克隆量表示代码获取活动，不能直接解释为成功安装人数、真实活跃用户数或产品质量。

首版采用你于 2026-10-16 提供的截图：648 次克隆、194 个独立克隆者，图表日期为 10 月 2 日至 15 日。自动更新需要在仓库 Actions secrets 中配置 `TRAFFIC_TOKEN`，权限限定 TOMC 的 `Administration: Read-only`；然后手动运行一次上面的 workflow。后续每天定时更新。未配置或读取失败时保留带日期的历史快照，不伪装成实时数据。
