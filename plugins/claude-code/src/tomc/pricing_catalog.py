"""Official, provenance-bearing reference rates. No inference or billing API calls."""

import hashlib
import json
import math
import re
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from html import unescape
from html.parser import HTMLParser
from pathlib import Path
from urllib.request import Request, urlopen

SOURCES = {
    "openai": "https://developers.openai.com/api/docs/pricing.md",
    "anthropic": "https://platform.claude.com/docs/en/about-claude/pricing",
    "deepseek": "https://api-docs.deepseek.com/quick_start/pricing/",
    "cursor": "https://cursor.com/docs/models-and-pricing",
}
BUNDLE = Path(__file__).parent / "data/pricing_snapshot.json"
CACHE = Path.home() / ".tomc/prices.json"


class Tables(HTMLParser):
    def __init__(self):
        super().__init__()
        self.tables, self.table, self.row, self.cell = [], None, None, None

    def handle_starttag(self, tag, attrs):
        if tag == "table":
            self.table = []
        elif tag == "tr":
            self.row = []
        elif tag in ("td", "th"):
            self.cell = ""

    def handle_data(self, data):
        if self.cell is not None:
            self.cell += data

    def handle_endtag(self, tag):
        if tag in ("td", "th") and self.cell is not None:
            if self.row is not None:
                self.row.append(self.cell.strip())
            self.cell = None
        elif tag == "tr" and self.row is not None:
            if self.table is not None:
                self.table.append(self.row)
            self.row = None
        elif tag == "table" and self.table is not None:
            self.tables.append(self.table)
            self.table = None


def money(text):
    if text.strip() in ("-", "—"):
        return None
    match = re.search(r"\$([0-9]+(?:\.[0-9]+)?)", text)
    if not match:
        raise ValueError("Unrecognized monetary cell")
    value = float(match[1])
    if not math.isfinite(value) or value < 0:
        raise ValueError("Invalid rate")
    return value


def slug(text):
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")


def entry(model, label, variant, input_rate, cached, output, condition, **extra):
    return dict(model=model, label=label, variant=variant, input=input_rate,
                cached=cached, output=output, condition=condition, **extra)


def parse(provider, raw):
    """Fail closed on missing headers; each provider updates as one atomic unit."""
    rows = []
    if provider == "openai":
        if "Short context: ≤272K input tokens. Long context: >272K input tokens." not in raw:
            raise ValueError("OpenAI context thresholds changed")
        for section in re.finditer(r"### (Standard|Batch|Flex|Fast) pricing data\s+(.*?)(?=\n###|\Z)", raw, re.S):
            tier, body = section[1], section[2]
            if "Short context cached input" not in body or "Long context output" not in body:
                raise ValueError("OpenAI pricing schema changed")
            for line in body.splitlines():
                cells = [c.strip() for c in line.strip().strip("|").split("|")]
                if len(cells) != 9 or not cells[0].startswith(("gpt-", "o1", "o3", "o4")):
                    continue
                model = cells[0].split(" (")[0]
                for band, offset in (("short", 1), ("long", 5)):
                    prices = [money(c) for c in cells[offset:offset+4]]
                    if prices[0] is None:
                        continue
                    rows.append(entry(model, model, f"{tier.lower()}-{band}",
                                      prices[0], prices[1], prices[3],
                                      f"{tier} · {'≤272K' if band == 'short' else '>272K'} 输入 · 全球基础价",
                                      cache_write=prices[2]))
    else:
        tables = Tables()
        tables.feed(raw)
        if provider == "anthropic":
            table = next(t for t in tables.tables if t[:2] == [
                ["Model", "Base tokens", "Prompt caching"],
                ["Name", "Input", "Output", "5m writes", "1h writes", "Hits and refreshes"]])
            for index, cells in enumerate(table):
                match = re.match(r"Claude (Fable|Opus|Sonnet|Haiku|Mythos) (\d+(?:\.\d+)?)", cells[0])
                if not match or len(cells) != 6:
                    continue
                label = match[0]
                model = slug(label)
                prices = [money(c) for c in cells[1:]]
                limited = "100,000" in cells[1]
                rows.append(entry(model, label, "standard", prices[0], prices[4], prices[1],
                                  "Standard · 全球基础价" + (" · ≤100K 输入" if limited else ""),
                                  cache_write=prices[2], cache_write_1h=prices[3]))
                if limited:
                    prices = [money(c) for c in table[index+1]]
                    if len(prices) != 5:
                        raise ValueError("Claude long-context row changed")
                    rows.append(entry(model, label, "standard-long", prices[0], prices[4], prices[1],
                                      "Standard · 全球基础价 · >100K 输入",
                                      cache_write=prices[2], cache_write_1h=prices[3]))
        elif provider == "deepseek":
            plain = unescape(re.sub(r"<[^>]+>", " ", raw))
            schedule = re.search(r"Peak hours are (.*?All other hours are off-peak.*?in full\.)", plain, re.S)
            if not schedule:
                raise ValueError("DeepSeek schedule changed")
            table = next(t for t in tables.tables if t[0][0] == "MODEL")
            models = [re.sub(r"\(\d+\)", "", x) for x in table[0][1:]]
            if models != ["deepseek-flash", "deepseek-v4-pro"]:
                raise ValueError("DeepSeek model columns changed")
            rates = {"peak": {}, "off-peak": {}}
            kind = None
            for cells in table:
                joined = " ".join(cells)
                if "CACHE HIT" in joined:
                    kind = "cached"
                elif "CACHE MISS" in joined:
                    kind = "input"
                elif "1M OUTPUT TOKENS" in joined:
                    kind = "output"
                for tier in rates:
                    if tier.upper() in cells and kind:
                        rates[tier][kind] = [money(c) for c in cells[-2:]]
            for tier, values in rates.items():
                for i, model in enumerate(models):
                    rows.append(entry(model, model, tier, values["input"][i], values["cached"][i],
                                      values["output"][i], "峰时" if tier == "peak" else "谷时",
                                      schedule="Peak hours are " + " ".join(schedule[1].split()) + " 按选择的时段折算历史，不自动回溯。"))
        elif provider == "cursor":
            seen = set()
            for table in tables.tables:
                if table[0] != ["Name", "Input", "Cache Write", "Cache Read", "Output"]:
                    continue
                for cells in table[1:]:
                    if len(cells) != 5 or cells[0] in seen:
                        continue
                    seen.add(cells[0])
                    model = slug(cells[0])
                    own = model.startswith(("grok-", "composer-"))
                    rows.append(entry(model, cells[0], "listed", money(cells[1]), money(cells[3]),
                                      money(cells[4]), "Cursor 公布基础价 · " + ("额外用量" if own else "第三方模型；基础上下文档位，长上下文需另核费率"),
                                      cache_write=money(cells[2]), own_model=own))
    if not rows or any(r["input"] is None or r["output"] is None for r in rows):
        raise ValueError("Missing input/output prices")
    for row in rows:
        row.update(provider=provider, key=f"{provider}:{row['model']}:{row['variant']}", source=SOURCES[provider])
    return rows


def read_catalog(path=None):
    for candidate in ((path or CACHE), BUNDLE):
        try:
            data = json.loads(candidate.read_text("utf-8"))
            if data.get("schema") == 1 and isinstance(data.get("providers"), dict):
                if candidate == BUNDLE:
                    for provider in data["providers"].values():
                        provider["status"] = "bundled"
                return data
        except (OSError, ValueError, AttributeError):
            pass
    return {"schema": 1, "providers": {}}


def all_rates(catalog=None):
    for provider in (catalog or read_catalog())["providers"].values():
        for row in provider.get("rates", []):
            yield {**row, "verified_at": provider["verified_at"],
                   "sync_status": provider.get("status", "bundled")}


def fetch(url):
    request = Request(url, headers={"User-Agent": "TOMC-price-sync/1.0"})
    with urlopen(request, timeout=20) as response:
        return response.read(4_000_000).decode("utf-8")


def sync(path=None, fetcher=fetch):
    """Network failure retains the old verification date, never silently refreshes it."""
    path = path or CACHE
    catalog = read_catalog(path)
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")

    def update(item):
        provider, url = item
        try:
            raw = fetcher(url)
            rates = parse(provider, raw)
            return provider, dict(rates=rates, verified_at=now, attempted_at=now,
                                  status="live", source=url, sha256=hashlib.sha256(raw.encode()).hexdigest())
        except Exception as exc:
            return provider, {**catalog["providers"].get(provider, {}), "attempted_at": now,
                              "status": "stale", "error": type(exc).__name__, "source": url}

    with ThreadPoolExecutor(max_workers=4) as pool:
        catalog["providers"].update(dict(pool.map(update, SOURCES.items())))
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(catalog, ensure_ascii=False, indent=2), "utf-8")
    temporary.replace(path)
    return catalog
