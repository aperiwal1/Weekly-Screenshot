import asyncio
import os
from datetime import datetime
from playwright.async_api import async_playwright

OUTPUT_DIR = "site"
os.makedirs(OUTPUT_DIR, exist_ok=True)

EARNINGS_PNG = os.path.join(OUTPUT_DIR, "earnings_calendar.png")
FX_PNG       = os.path.join(OUTPUT_DIR, "forexfactory_high_impact.png")

# ---------- helpers ----------

async def scroll_full_page(page, steps=12, delay=1.0):
    """Scrolls down the page to trigger lazy loading, then back to top."""
    for _ in range(steps):
        await page.evaluate("window.scrollBy(0, window.innerHeight)")
        await asyncio.sleep(delay)
    await page.evaluate("window.scrollTo(0, 0)")
    await asyncio.sleep(1)

# ---------- captures ----------

async def capture_earnings_calendar(context):
    """Pinned Tweet Earnings Calendar"""
    page = await context.new_page()
    print("[Earnings] Navigating…")
    await page.goto("https://x.com/eWhispers")
    await asyncio.sleep(6)

    tweet = await page.query_selector("article")
    if not tweet:
        print("[Earnings][WARN] No tweet found.")
        return False

    await tweet.screenshot(path=EARNINGS_PNG)
    print(f"[Earnings][OK] Saved: {EARNINGS_PNG}")
    await page.close()
    return True

async def capture_forexfactory_calendar(context):
    """ForexFactory Economic Calendar (High Impact, USD & CAD)"""
    url = "https://www.forexfactory.com/calendar?week=this"
    page = await context.new_page()
    print(f"[ForexFactory] Navigating… {url}")
    await page.goto(url)
    await asyncio.sleep(6)

    # Scroll through the whole week
    await scroll_full_page(page, steps=15, delay=1.2)

    # Screenshot the entire page
    await page.screenshot(path=FX_PNG, full_page=True)
    print(f"[ForexFactory][OK] Saved: {FX_PNG}")
    await page.close()
    return True

# ---------- main ----------

async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            viewport={"width": 1600, "height": 1600},
            user_agent=("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                        "AppleWebKit/537.36 (KHTML, like Gecko) "
                        "Chrome/120.0.0.0 Safari/537.36")
        )

        await capture_earnings_calendar(context)
        await capture_forexfactory_calendar(context)

        await browser.close()

if __name__ == "__main__":
    asyncio.run(main())
