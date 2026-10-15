"""Check the live offline tour and workbench. Requires optional Playwright + Chromium.

Start the local demo, then run this script. Captures only bundled synthetic input.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from urllib.parse import urlsplit

from playwright.sync_api import expect, sync_playwright

ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    """Verify real interactions, source provenance and narrow layouts without external requests."""
    errors, external_requests = [], []
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(
            viewport={"width": 1440, "height": 900},
            permissions=["clipboard-read", "clipboard-write"],
        )

        def route(request):
            if urlsplit(request.request.url).hostname in ("localhost", "127.0.0.1"):
                request.continue_()
            else:
                external_requests.append(urlsplit(request.request.url).hostname)
                request.abort()

        page.route("**/*", route)
        page.on("pageerror", lambda error: errors.append(str(error)))
        page.goto("http://127.0.0.1:7860", wait_until="networkidle")
        expect(page.locator("#easy-history textarea")).to_be_visible()
        expect(page.get_by_text("Compiler strategy", exact=True)).not_to_be_visible()
        page.locator("#easy-try").click()
        expect(page.locator("#easy-prompt textarea")).to_have_value(
            re.compile(
                r"[\s\S]*\[STATE\] backup_framework = Flask[\s\S]*\[STATE\] framework = FastAPI[\s\S]*"
            )
        )
        expect(page.locator("#easy-status")).to_contain_text("138 → 90")
        expect(page.locator("#easy-status")).to_contain_text("+48 tokens (+34.8%)")
        # A completed request can arrive after editing clears its output.
        for delay_ms in (20, 50):
            old_task = f"Previous task {delay_ms}: confirm attendance"
            new_task = f"Changed task {delay_ms}: confirm the venue"
            page.locator("#easy-task textarea").fill(old_task)
            page.locator("#easy-run").click()
            page.wait_for_timeout(delay_ms)
            page.locator("#easy-task textarea").fill(new_task)
            page.wait_for_timeout(1200)
            output = page.locator("#easy-prompt textarea").input_value()
            assert old_task not in output
            assert not output or new_task in output
        page.locator("#easy-history textarea").fill(
            "Attendance increased from 20 to 28. Two attendees need step-free access.\n"
            "Venue A has stairs. Venue B has a lift and holds 35 people.\n"
            "Venue B is available Friday afternoon but has not been booked."
        )
        page.locator("#easy-task textarea").fill(
            "Which venue fits, and what still needs to be done?"
        )
        page.locator("#easy-run").click()
        prompt = page.locator("#easy-prompt textarea")
        expect(prompt).to_have_value(re.compile(r"[\s\S]*has not been booked[\s\S]*"))
        page.locator("#easy-prompt").get_by_role("button", name="Copy", exact=True).click()
        copied = page.evaluate("navigator.clipboard.readText()")
        assert copied.replace("\r\n", "\n") == prompt.input_value()
        page.screenshot(path=str(ROOT / "assets/demo_desktop.png"), full_page=True)
        for width, height in ((390, 844), (320, 740)):
            page.set_viewport_size({"width": width, "height": height})
            page.evaluate("window.scrollTo(0,0)")
            assert page.evaluate("document.documentElement.scrollWidth") == width
            button = page.locator("#easy-run").bounding_box()
            assert button["y"] + button["height"] < height
            if width == 390:
                page.screenshot(path=str(ROOT / "assets/demo_mobile.png"), full_page=True)
        page.set_viewport_size({"width": 1440, "height": 900})
        page.locator("#easy-task textarea").fill("What should we book?")
        expect(prompt).to_have_value("")
        expect(page.locator("#easy-status")).to_contain_text("Inputs changed")
        page.get_by_text("Upload or try an example", exact=True).click()
        upload = '{"role":"user","content":"饮品：茶"}\r\n{"role":"user","content":"饮品：水"}'
        page.locator("#easy-upload input[type=file]").set_input_files(
            {"name": "synthetic.jsonl", "mimeType": "text/plain", "buffer": upload.encode()}
        )
        expect(page.locator("#easy-history textarea")).to_have_value(upload.replace("\r\n", "\n"))
        page.locator("#easy-run").click()
        expect(prompt).to_have_value(re.compile(r"[\s\S]*饮品：水[\s\S]*"))
        page.get_by_role("tab", name="Connect your assistant", exact=True).click()
        expect(page.get_by_text("python -m tomc setup --client codex", exact=False)).to_be_visible()
        page.get_by_role("tab", name="30-second tour", exact=True).click()
        cards = page.locator(".state-card")
        expect(cards).to_have_count(3)
        expect(cards.first).to_contain_text("backup_drink")
        summary = cards.first.locator("summary")
        summary.focus()
        summary.press("Enter")
        expect(cards.first.locator(".citations")).to_be_visible()
        expect(cards.first).to_contain_text("u2 · message 2, line 1")
        summary.press("Enter")
        page.locator(".hero h1").click()
        for width, height in ((390, 844), (320, 740)):
            page.set_viewport_size({"width": width, "height": height})
            assert page.evaluate("document.documentElement.scrollWidth") == width
        page.set_viewport_size({"width": 1440, "height": 900})
        for name, expected in (("When original words matter", "Some questions need"),):
            page.locator(".tour-controls input").click()
            page.get_by_role("option", name=name, exact=True).click()
            expect(page.locator(".tour-intro h2")).to_contain_text(expected)
        page.get_by_role("button", name="Try your own history").click()
        expect(page.locator("#easy-history textarea")).to_be_visible()
        page.get_by_role("tab", name="Workbench", exact=True).click()
        expect(page.locator("#source-input textarea")).to_be_visible()
        page.locator("#source-input textarea").fill(
            "drink = tea\nbackup_drink copies drink\ndrink = water"
        )
        expect(page.locator(".output-status").first).to_contain_text("Inputs changed")
        page.get_by_role("button", name="Compile memory").click()
        memory = page.locator("#memory-output textarea")
        expect(memory).to_have_value(re.compile(r"[\s\S]*\[STATE\] drink = water[\s\S]*"))
        expect(memory).to_have_value(re.compile(r"[\s\S]*\[STATE\] backup_drink = tea[\s\S]*"))
        assert memory.evaluate("el => el.scrollTop") == 0
        page.get_by_role("tab", name="Side-by-side", exact=True).click()
        page.get_by_role("button", name="Compare methods", exact=True).click()
        expect(page.locator("#compare-right textarea")).to_have_value(
            re.compile(r"[\s\S]*\[STATE\] drink = water[\s\S]*")
        )
        page.get_by_role("tab", name="03 / State & ledger", exact=True).click()
        for width in (390, 320):
            page.set_viewport_size({"width": width, "height": 844})
            assert page.evaluate("document.documentElement.scrollWidth") == width
        page.set_viewport_size({"width": 1440, "height": 900})
        page.get_by_role("tab", name="Research evidence", exact=True).click()
        expect(page.locator("#evidence-scores")).to_contain_text("Baseline / TOMC")
        expect(page.locator("#evidence-scores")).not_to_contain_text("Without / With TOMC")
        expect(page.locator("#evidence-scores")).to_contain_text("37.69 / 60.16")
        page.locator("#evidence-tier").get_by_label("1M", exact=True).check()
        expect(page.locator("#evidence-scores")).to_contain_text("24.67 / 58.69")
        expect(page.locator("#evidence-notes")).to_contain_text("200 empty memories")
        (ROOT / "outputs").mkdir(exist_ok=True)
        page.screenshot(path=str(ROOT / "outputs/research_desktop.png"), full_page=True)
        for width in (390, 320):
            page.set_viewport_size({"width": width, "height": 844})
            assert page.evaluate("document.documentElement.scrollWidth") == width
            if width == 390:
                page.screenshot(path=str(ROOT / "outputs/research_mobile.png"), full_page=True)
        page.get_by_text("Construction time and resource measurements", exact=True).click()
        expect(page.get_by_role("cell", name="4.21 s/call", exact=True)).to_be_visible()
        assert page.evaluate("document.documentElement.scrollWidth") == 320
        assert not errors
        assert not external_requests
        print(
            json.dumps(
                {
                    "tour": "real output on load; source expansion via keyboard; two paper examples",
                    "viewport_widths": [1440, 390, 320],
                    "horizontal_overflow": False,
                    "prepare_button_visible_without_scroll": True,
                    "easy_handoff": "one-click example; exact clipboard; late old responses never reappear after editing",
                    "upload": "JSONL imported and compiled",
                    "assistant_setup": "visible",
                    "compile": "edited input produced updated state and preserved snapshot",
                    "compare": "pass",
                    "research": "history selector updates scores; limits and resource measurements visible",
                    "page_errors": errors,
                    "external_requests": external_requests,
                },
                indent=2,
            )
        )
        browser.close()


if __name__ == "__main__":
    main()
