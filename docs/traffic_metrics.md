# Repository traffic and Stars

The homepage places Stars and cumulative recorded clones side by side, to the right of the centered TOMC logo. Both badges are generated in this repository, without a Shields.io dependency. Stars are a dated API snapshot and refresh with the daily workflow.

| Metric | Definition |
|---|---|
| Stars | GitHub repository API `stargazers_count` at collection time |
| Clones (total) | Sum of archived daily full-clone counts, counting each UTC date once; fetches excluded |
| Updated date | Collection date in UTC; see JSON files for exact timestamps |

## How cumulative clones work

GitHub's [Traffic API](https://docs.github.com/en/rest/metrics/traffic#get-repository-clones) returns a rolling 14-day window. We retain its daily records and calculate a cumulative total across archived dates. Dates remain included after they leave the API window. Newer observations of the same date replace older values, including corrections downward. Re-running the workflow does not add the same day again. Overlapping 14-day totals are never added together.

[`cumulative.json`](https://github.com/ZipengWu365/TOMC/blob/main/metrics/traffic/cumulative.json) contains the total and daily ledger. It is rebuilt from dated API files in [`snapshots`](https://github.com/ZipengWu365/TOMC/tree/main/metrics/traffic/snapshots), so the calculation is auditable. [`latest.json`](https://github.com/ZipengWu365/TOMC/blob/main/metrics/traffic/latest.json) retains the latest raw rolling-window snapshot; it is not the cumulative badge source. [`stars.json`](https://github.com/ZipengWu365/TOMC/blob/main/metrics/traffic/stars.json) stores the Star snapshot.

The first API archive was collected on **2026-10-16**, covering daily records from **2026-10-02 through 2026-10-15**, totaling **648 clones**. The earlier owner screenshot is retained for provenance but excluded from accumulation because it overlaps the API data and has no daily breakdown. The first nonzero archived day is October 6. The owner recalls making the repository public around October 10; that date has not been verified, and earlier recorded clones have not been discarded.

**Scope:** this is the cumulative count of recorded clones. It does not assert a verified all-time count since creation or public release. History unavailable before the first archive cannot be reconstructed. A collection outage longer than GitHub's retention window can leave unrecoverable gaps; the displayed total then includes only recorded dates. An omitted date is not fabricated as zero. The date shown on the homepage identifies the first recorded date, not the public-release date.

Automation, repeated clones and maintainer activity can contribute. These counts do not establish installations, active users or software quality. No IP addresses, account lists, notebook content or client telemetry are collected. Unique-cloner fields in raw API archives are not displayed on the homepage or summed across dates.

## Enable automatic collection

GitHub's [Traffic API](https://docs.github.com/en/rest/metrics/traffic#get-repository-clones) requires repository **Administration: read** for a fine-grained personal access token. The default Actions token does not provide that permission.

1. Create a [fine-grained token](https://github.com/settings/personal-access-tokens/new) with resource owner `ZipengWu365`, repository access limited to **TOMC**, and repository **Administration: Read-only**. Keep the automatically required metadata permission. This token does not need code-write permission. Choose an expiry and renew before it expires.
2. In [TOMC → Settings → Secrets and variables → Actions](https://github.com/ZipengWu365/TOMC/settings/secrets/actions), add repository secret **`TRAFFIC_TOKEN`**. Paste the token there, never into a README, issue or chat.
3. Open [Actions → Update clone traffic badges](https://github.com/ZipengWu365/TOMC/actions/workflows/traffic.yml) and select **Run workflow** on `main`.
4. Check that the collection step reports a successful collection and that `cumulative.json`, `stars.json` and the homepage update date refresh.

The workflow is scheduled daily at **06:23 UTC**; scheduled runs can be delayed. It uses the read-only secret for read-only Traffic and repository metadata requests. GitHub's separate built-in Actions token commits the aggregate data, SVG badges, dated captions and updated release hashes to `main`. Branch rules must allow that write. A conflicting push fails rather than overwriting another change; rerun the workflow after such a failure.

When the secret is missing, the workflow warns and retains the dated snapshot. Expired credentials, HTTP errors or malformed responses do not replace the saved counts with zero. A green workflow that says collection is not configured is not proof of a live refresh. The snapshot date remains visible so stale data is identifiable.

## 中文说明

首页采用左侧 Star us、中间 TOMC 标志、右侧 Stars 与累计 Clones 并排的布局。两个数字徽章都由仓库内脚本生成，随每日任务更新。

累计值按 UTC 日期汇总：同一天只记一次，新记录替换当天旧值；离开 GitHub 14 天窗口的旧日期仍永久保留。重复运行不会重复累加，GitHub 修正历史数据时累计值也会相应修正。

首次 API 记录覆盖 2026-10-02 至 2026-10-15，合计 648 次，最早非零记录是 10 月 6 日。公开日期约为 10 月 10 日是作者回忆，未据此删除更早的记录。徽章表示已记录数据的累计克隆量；未采集到的更早历史、长期中断后过期的日期无法补算。因此不宣称已验证仓库创建以来的完整总量，也不把克隆解释为安装人数或实际使用人数。

Actions secret `TRAFFIC_TOKEN` 限定 TOMC 的 `Administration: Read-only` 权限。每天 06:23 UTC 定时刷新（调度可能延迟）；凭据到期需续期。读取失败保留上次成功结果与日期。
