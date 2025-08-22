import asyncio
import os
import shutil
from datetime import datetime
from zoneinfo import ZoneInfo
from playwright.async_api import async_playwright

OUTPUT_DIR = "site"
os.makedirs(OUTPUT_DIR, exist_ok=True)

# Use New York date so filenames match your posting day
DATE_NY = datetime.now(ZoneInfo("America/New_York")).strftime("%Y-%m-%d")

# Dated filenames (immutable history)
EARNINGS_PNG_DATED = os.path.join(OUTPUT_DIR, f"pinned_tweet_{DATE_NY}.png")
FF_PNG_DATED       = os.path.join(OUTPUT_DIR, f"forexfactory_full_{DATE_NY}.png")

# “Latest” convenience copies (overwrite each run)
EARNINGS_PNG_LATEST = os.path.join(OUTPUT_DIR, "pinned_tweet_latest.png")
FF_PNG_LATEST       = os.path.join(OUTPUT_DIR, "forexfactory_full_latest.png")


async def scroll_full_page(page, steps=15, delay=1.0):
    """Scrolls down to trigger lazy-loading, then back to top."""
    for _ in range(steps):
        await page.evaluate("window.scrollBy(0, window.innerHeight)")
        await asyncio.sleep(delay)
    await page.evaluate("window.scrollTo(0, 0)")
    await asyncio.sleep(1)


async def capture_earnings_calendar(context):
    """Capture the first (pinned/top) tweet from @eWhispers."""
    page = await context.new_page()
    print("[Earnings] Navigating…")
    await page.goto("https://x.com/eWhispers")
    await asyncio.sleep(6)

    tweet = await page.query_selector("article")
    if not tweet:
        print("[Earnings][WARN] No tweet found; skipping.")
        await page.close()
        return False

    await tweet.screenshot(path=EARNINGS_PNG_DATED)
    # Update latest copy
    try:
        shutil.copyfile(EARNINGS_PNG_DATED, EARNINGS_PNG_LATEST)
    except Exception as e:
        print(f"[Earnings][WARN] Could not write latest copy: {e}")

    print(f"[Earnings][OK] Saved: {EARNINGS_PNG_DATED}")
    await page.close()
    return True


async def capture_forexfactory_fullpage(context):
    """Capture the entire ForexFactory 'This Week' calendar as a full-page PNG."""
    url = "https://www.forexfactory.com/calendar?week=this"
    page = await context.new_page()
    print(f"[FF] Navigating… {url}")
    await page.goto(url)
    await asyncio.sleep(6)

    # Accept cookies (best-effort)
    for sel in [
        'button:has-text("Accept All")',
        'button:has-text("Accept all")',
        'button:has-text("I Accept")',
        'button:has-text("Agree")',
        ('role', 'button', 'Accept'),
        '[aria-label*="Accept"]'
    ]:
        try:
            if isinstance(sel, tuple):
                _, role, name = sel
                await page.get_by_role(role, name=name).click(timeout=1500)
            else:
                await page.locator(sel).first.click(timeout=1500)
            await asyncio.sleep(1)
            break
        except:
            pass

    # Scroll to load the full week, then screenshot the ENTIRE page
    await scroll_full_page(page, steps=18, delay=0.9)
    await page.screenshot(path=FF_PNG_DATED, full_page=True)

    # Update latest copy
    try:
        shutil.copyfile(FF_PNG_DATED, FF_PNG_LATEST)
    except Exception as e:
        print(f"[FF][WARN] Could not write latest copy: {e}")

    print(f"[FF][OK] Saved: {FF_PNG_DATED}")
    await page.close()
    return True


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
        await capture_forexfactory_fullpage(context)

        await browser.close()

if __name__ == "__main__":
    asyncio.run(main())
