import asyncio
import os
from playwright.async_api import async_playwright
from datetime import datetime

OUTPUT_DIR = "site"
os.makedirs(OUTPUT_DIR, exist_ok=True)

PINNED_TWEET_PNG = os.path.join(OUTPUT_DIR, "pinned_tweet.png")
FF_CAL_PNG       = os.path.join(OUTPUT_DIR, "forexfactory_usd_cad_high.png")

async def capture_pinned_tweet(page):
    url = "https://x.com/eWhispers"
    print("[Pinned] Navigating…")
    await page.goto(url)
    await asyncio.sleep(6)
    print("[Pinned] Locating first tweet (pinned)…")
    tweet = await page.query_selector("article")
    if not tweet:
        print("[Pinned][ERROR] Could not find pinned tweet.")
        return False
    await tweet.screenshot(path=PINNED_TWEET_PNG)
    print(f"[Pinned][OK] Saved: {PINNED_TWEET_PNG}")
    return True

async def ff_take_any_screenshot(page):
    """Always save something to FF_CAL_PNG (calendar section if possible; otherwise full page)."""
    print("[FF] Fallback capture of calendar…")
    # Try common containers first
    for sel in ['div.calendar__table', 'main', '[data-ff="calendar"]', '#calendars', '.calendar']:
        try:
            el = await page.query_selector(sel)
            if el:
                await el.screenshot(path=FF_CAL_PNG)
                print(f"[FF][OK] Saved (container): {FF_CAL_PNG}")
                return True
        except:
            pass
    # Full page fallback
    await page.screenshot(path=FF_CAL_PNG, full_page=True)
    print(f"[FF][OK] Saved (full page): {FF_CAL_PNG}")
    return True

async def capture_forexfactory_filtered(context):
    url = "https://www.forexfactory.com/calendar?week=this"
    page = await context.new_page()
    print("[FF] Navigating…")
    await page.goto(url)
    await asyncio.sleep(6)

    # Try cookie/consent
    for sel in [
        'text="Accept All"', 'text="Accept all"', 'text="I Accept"', 'text="Agree"', 
        'button:has-text("Accept")'
    ]:
        try:
            btn = await page.query_selector(sel)
            if btn:
                await btn.click()
                await asyncio.sleep(1)
                print("[FF] Accepted cookies.")
                break
        except:
            pass

    # Try to open filters
    print("[FF] Opening filters…")
    opened = False
    try:
        await page.get_by_role("button", name=lambda n: n and "filter" in n.lower()).click(timeout=4000)
        opened = True
    except:
        for sel in ['button:has-text("Filter")', 'button[class*="filter"]', '[aria-label*="Filter"]', '[title*="Filter"]']:
            try:
                await page.locator(sel).first.click(timeout=3000)
                opened = True
                break
            except:
                continue

    if not opened:
        print("[FF][WARN] Could not open Filters panel. Capturing without filters.")
        ok = await ff_take_any_screenshot(page)
        await page.close()
        return ok

    await asyncio.sleep(1)

    # Clear all
    print("[FF] Clearing all filters…")
    cleared = False
    for sel in ['text=Clear All', 'button:has-text("Clear All")']:
        try:
            await page.locator(sel).first.click(timeout=3000)
            cleared = True
            await asyncio.sleep(1)
            break
        except:
            continue
    if not cleared:
        print("[FF][WARN] Clear All not found, continuing anyway.")

    # Select USD + CAD
    print("[FF] Selecting currencies USD + CAD…")
    for curr in ["USD", "CAD"]:
        selected = False
        try:
            await page.locator(f'label:has-text("{curr}")').first.click(timeout=2000)
            selected = True
        except:
            try:
                await page.get_by_role("checkbox", name=curr).check(timeout=2000)
                selected = True
            except:
                pass
        if not selected:
            print(f"[FF][WARN] Could not select currency: {curr}")

    # Impact = High only
    print("[FF] Selecting Impact: High…")
    impact_selected = False
    for name in ["High", "High Impact", "High (Red)"]:
        try:
            await page.locator(f'label:has-text("{name}")').first.click(timeout=2000)
            impact_selected = True
            break
        except:
            try:
                await page.get_by_role("checkbox", name=lambda n: n and "high" in n.lower()).check(timeout=2000)
                impact_selected = True
                break
            except:
                pass
    if not impact_selected:
        print("[FF][WARN] Could not confirm High impact selection.")

    # Apply filter
    print("[FF] Applying filter…")
    applied = False
    for sel in ['text=Apply Filter', 'button:has-text("Apply Filter")', '[type="submit"]:has-text("Apply")']:
        try:
            await page.locator(sel).first.click(timeout=3000)
            applied = True
            break
        except:
            continue
    if not applied:
        print("[FF][WARN] Could not click Apply Filter; capturing anyway.")
        ok = await ff_take_any_screenshot(page)
        await page.close()
        return ok

    await asyncio.sleep(4)

    # Ensure calendar area is visible (scroll to top just in case)
    try:
        await page.evaluate("window.scrollTo(0, 0)")
    except:
        pass

    ok = await ff_take_any_screenshot(page)
    await page.close()
    return ok

async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            viewport={'width': 1600, 'height': 1600},
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            )
        )

        # Pinned tweet
        page = await context.new_page()
        await capture_pinned_tweet(page)
        await page.close()

        # ForexFactory calendar
        await capture_forexfactory_filtered(context)

        await browser.close()

if __name__ == "__main__":
    asyncio.run(main())
