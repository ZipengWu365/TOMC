"""Check the live offline demo in a real browser. Requires optional Playwright + Chromium.

Start the local demo (`python -m demo.app`), then run this script. It types and clicks
through both language pages, blocks every request that is not to the local server, and
checks narrow layouts. Only bundled synthetic input is used. Nothing is written into the
repository unless you pass a screenshot path, for example:

    python scripts/browser_smoke.py --screenshot assets/demo_desktop.png \
        --mobile-screenshot assets/demo_mobile.png
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from urllib.parse import urlsplit

from playwright.sync_api import expect, sync_playwright

ROOT = Path(__file__).resolve().parents[1]
MINUS = "−"
INK = "rgb(23, 42, 39)"
NARROW = ((390, 844), (320, 740))


def package_version() -> str:
    """The version the footer must show, read from the checkout without importing it."""
    text = (ROOT / "src/tomc/__init__.py").read_text(encoding="utf-8")
    return re.search(r'__version__ = "([^"]+)"', text)[1]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--url", default="http://127.0.0.1:7860", help="local demo address")
    parser.add_argument("--screenshot", type=Path, help="save the desktop first view here")
    parser.add_argument("--mobile-screenshot", type=Path, help="save the 390 px first view here")
    parser.add_argument(
        "--research-screenshots", type=Path, help="folder for research tab screenshots"
    )
    parser.add_argument(
        "--executable-path", help="Chromium binary to use instead of Playwright's own download"
    )
    return parser.parse_args()


def no_horizontal_scroll(page, label: str) -> None:
    """Every narrow width fits without a sideways page scroll."""
    for width, height in NARROW:
        page.set_viewport_size({"width": width, "height": height})
        page.evaluate("window.scrollTo(0, 0)")
        scroll = page.evaluate("document.documentElement.scrollWidth")
        assert scroll == width, f"{label}: {scroll}px wide at {width}px"
    page.set_viewport_size({"width": 1440, "height": 900})


def main() -> None:
    """Verify real interactions, source provenance and narrow layouts without external requests."""
    args = parse_args()
    if urlsplit(args.url).hostname not in ("localhost", "127.0.0.1"):
        raise SystemExit("Run the demo locally and point --url at 127.0.0.1 or localhost.")
    errors, external_requests = [], []
    with sync_playwright() as p:
        launch = {"headless": True}
        if args.executable_path:
            launch["executable_path"] = args.executable_path
        browser = p.chromium.launch(**launch)
        # A dark system theme must still give the fixed cream page with dark text.
        context = browser.new_context(
            viewport={"width": 1440, "height": 900},
            color_scheme="dark",
            permissions=["clipboard-read", "clipboard-write"],
        )
        page = context.new_page()

        def route(request):
            if urlsplit(request.request.url).hostname in ("localhost", "127.0.0.1"):
                request.continue_()
            else:
                external_requests.append(urlsplit(request.request.url).hostname)
                request.abort()

        context.route("**/*", route)
        page.on("pageerror", lambda error: errors.append(str(error)))
        page.goto(args.url, wait_until="networkidle")

        # Chinese by default, light even on a dark system, result already on screen.
        status = page.locator("#easy-status-zh")
        expect(status).to_be_visible()
        assert page.evaluate("document.querySelector('.dark') === null")
        assert page.locator(".page-zh .hero h1").evaluate("e => getComputedStyle(e).color") == INK
        expect(page.locator(".page-zh .hero h1")).to_contain_text("改过的事")
        expect(page.locator("#lang-switch input:checked")).to_have_value("中文")
        big = status.locator(".big")
        expect(big).to_contain_text(re.compile(rf"少发 [\d,]+ token（{MINUS}\d+%）"))
        expect(big).to_contain_text("估算")
        assert "+" not in big.inner_text()
        expect(status.locator(".found")).to_contain_text("framework = Litestar")
        expect(status.locator(".found")).to_contain_text("db = postgres")
        expect(status.locator(".found")).to_contain_text("第 234 行")
        strip = page.locator("#easy-strip-zh")
        expect(strip).to_contain_text("framework = Litestar")
        expect(strip).to_contain_text("行没带上")
        prompt = page.locator("#easy-prompt-zh textarea")
        expect(prompt).to_have_value(re.compile(r"[\s\S]*\[STATE\] framework = Litestar[\s\S]*"))
        expect(page.locator(".page-zh .footer")).to_contain_text(f"v{package_version()}")
        expect(page.get_by_text("整理方法", exact=True)).not_to_be_visible()
        if args.screenshot:
            page.screenshot(path=str(args.screenshot))

        # The first thing on a phone is the big number, and nothing scrolls sideways.
        for width, height in NARROW:
            page.set_viewport_size({"width": width, "height": height})
            page.evaluate("window.scrollTo(0, 0)")
            assert page.evaluate("document.documentElement.scrollWidth") == width
            box = big.bounding_box()
            assert box["y"] + box["height"] < height, f"big number below the fold at {width}px"
            if width == 390 and args.mobile_screenshot:
                page.screenshot(path=str(args.mobile_screenshot))
        page.set_viewport_size({"width": 1440, "height": 900})

        # 换个例子 cycles through the bundled examples and prepares each one.
        history = page.locator("#easy-history-zh textarea")
        page.locator("#easy-try-zh").click()
        expect(history).to_have_value(re.compile(r"^Session 1"))
        expect(big).to_contain_text(f"（{MINUS}")
        page.locator("#easy-try-zh").click()
        expect(history).to_have_value(re.compile(r"^framework = Flask"))
        expect(big).to_contain_text("没有变化")
        expect(prompt).to_have_value(re.compile(r"[\s\S]*framework = FastAPI[\s\S]*"))

        # A completed request can arrive after editing clears its output.
        task = page.locator("#easy-task-zh textarea")
        for delay_ms in (20, 50):
            old_task = f"旧问题 {delay_ms}：确认人数"
            new_task = f"新问题 {delay_ms}：确认场地"
            task.fill(old_task)
            page.locator("#easy-run-zh").click()
            page.wait_for_timeout(delay_ms)
            task.fill(new_task)
            page.wait_for_timeout(1200)
            output = prompt.input_value()
            assert old_task not in output
            assert not output or new_task in output

        history.fill(
            "Attendance increased from 20 to 28. Two attendees need step-free access.\n"
            "Venue A has stairs. Venue B has a lift and holds 35 people.\n"
            "Venue B is available Friday afternoon but has not been booked."
        )
        task.fill("Which venue fits, and what still needs to be done?")
        page.locator("#easy-run-zh").click()
        expect(prompt).to_have_value(re.compile(r"[\s\S]*has not been booked[\s\S]*"))
        expect(big).to_contain_text("没有变化")
        page.locator("#easy-prompt-zh").get_by_role("button", name="Copy", exact=True).click()
        copied = page.evaluate("navigator.clipboard.readText()")
        assert copied.replace("\r\n", "\n") == prompt.input_value()
        task.fill("该订哪个场地？")
        expect(prompt).to_have_value("")
        expect(status).to_contain_text("输入改了")
        page.get_by_text("上传文件或选例子", exact=True).click()
        upload = '{"role":"user","content":"饮品：茶"}\r\n{"role":"user","content":"饮品：水"}'
        page.locator("#easy-upload-zh input[type=file]").set_input_files(
            {"name": "synthetic.jsonl", "mimeType": "text/plain", "buffer": upload.encode()}
        )
        expect(history).to_have_value(upload.replace("\r\n", "\n"))
        page.locator("#easy-run-zh").click()
        expect(prompt).to_have_value(re.compile(r"[\s\S]*饮品：水[\s\S]*"))

        # The visible switch shows the English page and hides the Chinese one.
        page.locator("#lang-switch").get_by_text("English", exact=True).click()
        status = page.locator("#easy-status-en")
        expect(status).to_be_visible()
        expect(page.locator("#easy-status-zh")).not_to_be_visible()
        big = status.locator(".big")
        expect(big).to_contain_text(re.compile(rf"[\d,]+ fewer tokens \({MINUS}\d+%\)"))
        expect(big).to_contain_text("estimate")
        expect(status.locator(".found")).to_contain_text("framework = Litestar")
        expect(page.locator(".page-en .hero h1")).to_contain_text("When a fact changes")
        expect(page.locator(".page-en .footer")).to_contain_text(f"v{package_version()}")
        page.locator("#easy-try-en").click()
        expect(page.locator("#easy-history-en textarea")).to_have_value(re.compile(r"^Session 1"))
        expect(big).to_contain_text(f"fewer tokens ({MINUS}")

        page.get_by_role("tab", name="Connect your assistant", exact=True).click()
        expect(page.get_by_text("python -m tomc setup --client codex", exact=False)).to_be_visible()

        # The tour leads with a case that compresses; the case that grows sits under Limits.
        page.get_by_role("tab", name="30-second tour", exact=True).click()
        story = page.locator(".page-en .prose.tour-story").first
        expect(story.locator(".tour-measure")).to_contain_text("662 → 58")
        expect(story.locator(".tour-measure")).to_contain_text(f"{MINUS}91%")
        cards = story.locator(".state-card")
        expect(cards).to_have_count(5)
        expect(cards.first).to_contain_text("backup_venue")
        summary = cards.first.locator("summary")
        summary.focus()
        summary.press("Enter")
        expect(cards.first.locator(".citations")).to_be_visible()
        expect(cards.first).to_contain_text("u24 · message 19, line 1")
        summary.press("Enter")
        no_horizontal_scroll(page, "tour")
        page.locator(".page-en .tour-controls input").click()
        page.get_by_role("option", name="Changing preferences", exact=True).click()
        expect(story.locator(".tour-intro h2")).to_contain_text("Preferences change")
        page.get_by_text("Limits: very short chats", exact=True).click()
        expect(page.locator(".page-en .prose.limits-note")).to_contain_text(
            "very short chats don't need compression"
        )
        expect(page.locator(".page-en .prose.tour-story").nth(1)).to_contain_text("31 → 36")
        page.get_by_role("button", name="Try your own history").click()
        expect(page.locator("#easy-history-en textarea")).to_be_visible()

        page.get_by_role("tab", name="Workbench", exact=True).click()
        source = page.locator("#source-input-en textarea")
        expect(source).to_be_visible()
        # Opening the tab is not an edit.
        expect(page.locator(".page-en .output-status").first).to_contain_text(
            "Output matches the loaded example."
        )
        source.fill("drink = tea\nbackup_drink copies drink\ndrink = water")
        expect(page.locator(".page-en .output-status").first).to_contain_text("Inputs changed")
        page.get_by_role("button", name="Compile memory").click()
        memory = page.locator("#memory-output-en textarea")
        expect(memory).to_have_value(re.compile(r"[\s\S]*\[STATE\] drink = water[\s\S]*"))
        expect(memory).to_have_value(re.compile(r"[\s\S]*\[STATE\] backup_drink = tea[\s\S]*"))
        assert memory.evaluate("el => el.scrollTop") == 0
        page.get_by_role("tab", name="Side-by-side", exact=True).click()
        page.get_by_role("button", name="Compare methods", exact=True).click()
        expect(page.locator("#compare-right-en textarea")).to_have_value(
            re.compile(r"[\s\S]*\[STATE\] drink = water[\s\S]*")
        )
        page.get_by_role("tab", name="03 / State & ledger", exact=True).click()
        no_horizontal_scroll(page, "workbench")

        page.get_by_role("tab", name="Research evidence", exact=True).click()
        scores = page.locator(".page-en .prose.evidence-scores")
        expect(scores).to_contain_text("Baseline / TOMC")
        expect(scores).not_to_contain_text("Without / With TOMC")
        expect(scores).to_contain_text("37.69 / 60.16")
        page.locator(".page-en .evidence-tier").get_by_label("1M", exact=True).check()
        expect(scores).to_contain_text("24.67 / 58.69")
        expect(page.locator(".page-en .prose.evidence-notes")).to_contain_text("200 empty memories")
        if args.research_screenshots:
            args.research_screenshots.mkdir(parents=True, exist_ok=True)
            page.screenshot(
                path=str(args.research_screenshots / "research_desktop.png"), full_page=True
            )
        no_horizontal_scroll(page, "research")
        if args.research_screenshots:
            page.set_viewport_size({"width": 390, "height": 844})
            page.screenshot(
                path=str(args.research_screenshots / "research_mobile.png"), full_page=True
            )
        page.set_viewport_size({"width": 320, "height": 740})
        page.get_by_text("Construction time and resource measurements", exact=True).click()
        expect(page.get_by_role("cell", name="4.21 s/call", exact=True)).to_be_visible()
        assert page.evaluate("document.documentElement.scrollWidth") == 320

        # ?lang=en opens the English page directly.
        direct = context.new_page()
        direct.on("pageerror", lambda error: errors.append(str(error)))
        direct.goto(args.url.rstrip("/") + "/?lang=en", wait_until="networkidle")
        expect(direct.locator("#easy-status-en")).to_be_visible()
        expect(direct.locator("#lang-switch input:checked")).to_have_value("English")
        assert direct.evaluate("document.querySelector('.dark') === null")

        assert not errors, errors
        assert not external_requests, external_requests
        print(
            json.dumps(
                {
                    "first_view": "Chinese; live sample result with a minus sign and 估算; "
                    "found framework = Litestar and db = postgres with line numbers",
                    "dark_system_theme": "page stays light",
                    "footer_version": package_version(),
                    "viewport_widths": [1440, 390, 320],
                    "horizontal_overflow": False,
                    "big_number_visible_without_scroll": True,
                    "next_example": "cycles and prepares each example",
                    "easy_handoff": "exact clipboard; late old responses never reappear after editing",
                    "upload": "JSONL imported and compiled",
                    "language_switch": "switch and ?lang=en both show the English page",
                    "assistant_setup": "visible",
                    "tour": "compressing case first; keyboard source expansion; growing case under Limits",
                    "compile": "edited input produced updated state and preserved snapshot",
                    "compare": "pass",
                    "research": "history selector updates scores; resource measurements visible",
                    "page_errors": errors,
                    "external_requests": external_requests,
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        browser.close()


if __name__ == "__main__":
    main()
