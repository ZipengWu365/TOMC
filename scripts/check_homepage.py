"""Check bilingual homepage links, local anchors, images and generated markers offline."""

from __future__ import annotations

import re
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import unquote, urlsplit

ROOT = Path(__file__).resolve().parents[1]
PAGES = ("README.md", "README_zh.md")


class Links(HTMLParser):
    def __init__(self):
        super().__init__()
        self.links = []
        self.ids = []
        self.unlabelled = []

    def handle_starttag(self, tag, attrs):
        values = dict(attrs)
        if "id" in values:
            self.ids.append(values["id"])
        for attr in ("href", "src", "srcset"):
            if values.get(attr):
                self.links.append(values[attr].split()[0])
        if tag == "img" and not values.get("alt"):
            self.unlabelled.append(values.get("src", "unknown image"))


def strip_fences(text):
    return re.sub(r"^```[^\n]*\n.*?^```\s*$", "", text, flags=re.M | re.S)


def anchors(text):
    visible = strip_fences(text)
    parser = Links()
    parser.feed(visible)
    result, seen = set(parser.ids), {}
    for heading in re.findall(r"^#{1,6}\s+(.+?)\s*#*\s*$", visible, flags=re.M):
        heading = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", heading)
        slug = re.sub(r"[^\w\- ]", "", heading.lower()).replace(" ", "-")
        count = seen.get(slug, 0)
        seen[slug] = count + 1
        result.add(f"{slug}-{count}" if count else slug)
    return result


def check():
    errors, total = [], 0
    for name in PAGES:
        path = ROOT / name
        text = path.read_text(encoding="utf-8")
        parser = Links()
        parser.feed(strip_fences(text))
        urls = parser.links + re.findall(r"\]\(([^\s)]+)", strip_fences(text))
        for url in urls:
            total += 1
            parts = urlsplit(url)
            if parts.scheme or parts.netloc:
                continue
            target = path.parent / unquote(parts.path) if parts.path else path
            if not target.exists():
                errors.append(f"{name}: missing {url}")
            elif parts.fragment and target.suffix == ".md":
                if unquote(parts.fragment) not in anchors(target.read_text(encoding="utf-8")):
                    errors.append(f"{name}: missing anchor {url}")
        if len(parser.ids) != len(set(parser.ids)):
            errors.append(f"{name}: duplicate explicit anchor")
        if parser.unlabelled:
            errors.append(f"{name}: missing image alt: {parser.unlabelled}")
        for start, end in (
            ("<!-- BEAM_TABLE_START -->", "<!-- BEAM_TABLE_END -->"),
            ("<!-- traffic-status:start -->", "<!-- traffic-status:end -->"),
            ("<!-- community-entry:start -->", "<!-- community-entry:end -->"),
        ):
            if (
                text.count(start) != 1
                or text.count(end) != 1
                or text.index(start) >= text.index(end)
            ):
                errors.append(f"{name}: invalid generated markers {start}")
        if len(re.findall(r"^```", text, flags=re.M)) % 2:
            errors.append(f"{name}: unclosed code fence")
        if text.count("<details>") != text.count("</details>"):
            errors.append(f"{name}: unbalanced details")
        if "@@" in text:
            errors.append(f"{name}: unresolved template marker")
    if errors:
        raise SystemExit("\n".join(errors))
    print(f"Homepage checks passed: {len(PAGES)} pages, {total} link references.")


if __name__ == "__main__":
    check()
