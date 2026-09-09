from __future__ import annotations

import asyncio
from pathlib import Path

from playwright.async_api import (
    async_playwright,
)


class BrowserRuntime:
    async def _run(
        self,
        url,
        action="text",
        selector=None,
        text=None,
        screenshot=None,
    ):
        async with async_playwright() as p:
            browser = await p.chromium.launch(
                headless=True
            )

            page = await browser.new_page()

            await page.goto(
                url,
                wait_until="domcontentloaded",
                timeout=60000,
            )

            if action == "title":
                result = await page.title()

            elif action == "text":
                result = await page.locator(
                    "body"
                ).inner_text()

            elif action == "click":
                if not selector:
                    raise ValueError(
                        "selector required"
                    )

                await page.click(
                    selector
                )

                await page.wait_for_timeout(
                    1000
                )

                result = await page.locator(
                    "body"
                ).inner_text()

            elif action == "fill":
                if not selector:
                    raise ValueError(
                        "selector required"
                    )

                await page.fill(
                    selector,
                    text or "",
                )

                result = "FILL=PASS"

            elif action == "screenshot":
                path = Path(
                    screenshot
                    or "/tmp/nexus_browser.png"
                )

                await page.screenshot(
                    path=str(path),
                    full_page=True,
                )

                result = (
                    f"SCREENSHOT={path}"
                )

            else:
                raise ValueError(
                    f"unknown action: {action}"
                )

            await browser.close()

            return result


def run_browser(
    url,
    action="text",
    selector=None,
    text=None,
    screenshot=None,
):
    return asyncio.run(
        BrowserRuntime()._run(
            url,
            action,
            selector,
            text,
            screenshot,
        )
    )
