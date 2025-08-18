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

async def capture_forexfactory_filtered(context):
    """
    Filters: Impact = High only, Currencies = USD + CAD, on 'this week' view.
    """
    url = "https://www.forexfactory.com/calendar?week=this"
    page = await context.new_page()
    print("[FF] Navigating…")
    await page.goto(url)
    await asyncio.sleep(5)

    # Handle cookie consent if present (best-effort)
    for sel in [
        'text="Accept All"', 'text="Accept all"', 'text="I Accept"', 'text="Agree"', 
        'button:has-text("Accept")'
    ]:
        try:
            btn = await page.query_selector(sel)
            if btn:
                await btn.click()
                await asyncio.sleep(1)
                break
        except:
            pass

    # Open Filters (use robust role-based locator first)
    print("[FF] Opening filters…")
    opened = False
    try:
        await page.get_by_role("button", name=lambda n: n and "filter" in n.lower()).click(timeout=5000)
        opened = True
    except:
        # fallback 1: visible text
        try:
            await page.locator('button:has-text("Filter")').first.click(timeout=5000)
            opened = True
        except:
            # fallback 2: any button with funnel icon-like class name
            try:
                await page.locator('button[class*="filter"]').first.click(timeout=5000)
                opened = True
            except:
                pass

    if not opened:
        print("[FF][ERROR] Could not open the Filters panel.")
        await page.close()
        return False

    await asyncio.sleep(1)

    # Clear all first (so only our choices apply)
    print("[FF] Clearing all filters…")
    try:
        # There can be multiple 'Clear All'—click the first visible one
        await page.locator('text=Clear All').first.click(timeout=5000)
        await asyncio.sleep(1)
    except:
        print("[FF] 'Clear All' not found; continuing.")

    # Select currencies USD & CAD
    print("[FF] Selecting currencies USD + CAD…")
    # Try label text and checkbox roles robustly
    for curr in ["USD", "CAD"]:
        selected = False
        try:
            await page.locator(f'label:has-text("{curr}")').first.click(timeout=3000)
            selected = True
        except:
            try:
                await page.get_by_role("checkbox", name=curr).check(timeout=3000)
                selected = True
            except:
                pass
        if not selected:
            print(f"[FF][WARN] Could not select currency: {curr}")

    # Select Impact = High only (red)
    print("[FF] Selecting Impact: High…")
    impact_selected = False
    for name in ["High", "High Impact", "High (Red)"]:
        try:
            await page.locator(f'label:has-text("{name}")').first.click(timeout=3000)
            impact_selected = True
            break
        except:
            try:
                await page.get_by_role("checkbox", name=lambda n: n and "high" in n.lower()).check(timeout=3000)
                impact_selected = True
                break
            except:
                pass
    if not impact_selected:
        print("[FF][WARN] Could not positively confirm High impact selection.")

    # Apply filter
    print("[FF] Applying filter…")
    applied = False
    for sel in ['text=Apply Filter', 'button:has-text("Apply Filter")']:
        try:
            await page.locator(sel).first.click(timeout=5000)
            applied = True
            break
        except:
            pass

    if not applied:
        print("[FF][ERROR] Could not find/apply the Apply Filter button.")
        await page.close()
        return False

    await asyncio.sleep(3)

    # Try to screenshot the main calendar area (fallback to full page)
    print("[FF] Capturing screenshot…")
    saved = False
    for cal_sel in [
        'div.calendar__table',  # guess for a calendar container
        'main',                 # main content
        '[data-ff="calendar"]'  # hypothetical data attribute
    ]:
        try:
            cal = await page.query_selector(cal_sel)
            if cal:
                await cal.screenshot(path=FF_CAL_PNG)
                saved = True
                break
        except:
            pass

    if not saved:
        await page.screenshot(path=FF_CAL_PNG, full_page=True)

    print(f"[FF][OK] Saved: {FF_CAL_PNG}")
    await page.close()
    return True

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

        # ForexFactory (USD, CAD, Impact High)
        await capture_forexfactory_filtered(context)

        await browser.close()

if __name__ == "__main__":
    asyncio.run(main())
