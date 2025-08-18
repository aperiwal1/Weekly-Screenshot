import asyncio
import os
from playwright.async_api import async_playwright

OUTPUT_DIR = "site"
os.makedirs(OUTPUT_DIR, exist_ok=True)

PINNED_TWEET_PNG = os.path.join(OUTPUT_DIR, "pinned_tweet.png")
TV_CAL_PNG       = os.path.join(OUTPUT_DIR, "tradingview_usd_cad_high.png")

# ---------- Helpers ----------

async def safe_click(page, selectors, timeout=4000):
    """Try a list of selectors until one clicks."""
    for sel in selectors:
        try:
            await page.locator(sel).first.click(timeout=timeout)
            return True
        except:
            try:
                # try get_by_role name match variant "role|name" tuple
                if isinstance(sel, tuple) and sel and sel[0] == "role":
                    _, role, name = sel
                    await page.get_by_role(role, name=name).click(timeout=timeout)
                    return True
            except:
                pass
    return False

async def safe_check(page, selectors, timeout=4000):
    for sel in selectors:
        try:
            await page.locator(sel).first.check(timeout=timeout)
            return True
        except:
            try:
                if isinstance(sel, tuple) and sel and sel[0] == "role":
                    _, role, name = sel
                    await page.get_by_role(role, name=name).check(timeout=timeout)
                    return True
            except:
                pass
    return False

# ---------- Captures ----------

async def capture_pinned_tweet(context):
    page = await context.new_page()
    print("[Pinned] Navigating…")
    await page.goto("https://x.com/eWhispers")
    await asyncio.sleep(6)

    print("[Pinned] Locating first tweet (pinned)…")
    tweet = await page.query_selector("article")
    if not tweet:
        print("[Pinned][WARN] Pinned tweet not found; skipping.")
        await page.close()
        return False

    await tweet.screenshot(path=PINNED_TWEET_PNG)
    print(f"[Pinned][OK] Saved: {PINNED_TWEET_PNG}")
    await page.close()
    return True

async def capture_tradingview_calendar(context):
    """
    TradingView economic calendar, filters:
      - Date range: This week
      - Importance: High
      - Currencies: USD + CAD
    """
    # Try two known calendar URLs; first one usually works.
    urls = [
        "https://www.tradingview.com/markets/economic-calendar/",
        "https://www.tradingview.com/economic-calendar/"
    ]

    page = await context.new_page()

    loaded = False
    for url in urls:
        print(f"[TV] Navigating… {url}")
        await page.goto(url)
        await asyncio.sleep(6)

        # Accept cookies if shown (best-effort)
        for sel in [
            'button:has-text("Accept all")',
            'button:has-text("Accept All")',
            'button:has-text("I accept")',
            'button:has-text("Agree")',
            ('role', 'button', 'Accept'),
        ]:
            if await safe_click(page, [sel], timeout=2000):
                await asyncio.sleep(1)
                break

        # Heuristic: look for the calendar container to confirm page shape
        if await page.query_selector("section:has(table), div:has(table), main"):
            loaded = True
            break

    if not loaded:
        print("[TV][WARN] Calendar shell not detected; will still attempt filters.")

    # Open filters / settings
    print("[TV] Opening filters/settings…")
    opened = await safe_click(page, [
        ('role', 'button', 'Filter'),
        'button:has-text("Filter")',
        'button:has-text("Filters")',
        'button[aria-label*="Filter"]',
        'button[title*="Filter"]',
        'button:has(svg)',
    ], timeout=4000)
    if not opened:
        print("[TV][WARN] Could not find Filters button. Continuing anyway.")

    await asyncio.sleep(1)

    # Date range: "This week"
    print("[TV] Setting date range: This week…")
    date_set = False
    # Open date menu if present
    if await safe_click(page, [
        ('role', 'button', 'Date'), 'button:has-text("Date")',
        'button[aria-label*="Date"]', '[data-name*="date"]'
    ], timeout=1500):
        await asyncio.sleep(0.5)
        date_set = await safe_click(page, [
            ('role', 'option', 'This week'),
            'div[role="option"]:has-text("This week")',
            'li:has-text("This week")',
            'button:has-text("This week")'
        ], timeout=2000)
    else:
        # Some UIs expose quick chips directly
        date_set = await safe_click(page, [
            'button:has-text("This week")',
            ('role', 'button', 'This week')
        ], timeout=2000)

    if not date_set:
        print("[TV][WARN] Date range 'This week' not set.")

    # Importance: High only
    print("[TV] Selecting Impact: High…")
    imp_ok = (
        await safe_click(page, [
            ('role', 'button', 'Importance'),
            'button:has-text("Importance")',
            '[data-name*="importance"]',
        ], timeout=1500)
        or True  # sometimes chips already visible
    )
    # Now choose High
    high_ok = await safe_click(page, [
        ('role', 'checkbox', 'High'),
        'label:has-text("High")',
        'button:has-text("High")',
        '[aria-label*="High"]',
    ], timeout=2000)
    if not high_ok:
        print("[TV][WARN] Could not confirm High selection.")

    # Currencies: USD + CAD
    print("[TV] Selecting currencies: USD + CAD…")
    # Sometimes there's a "Currencies" filter, or a search box.
    # Try opening currency filter panel:
    await safe_click(page, [
        ('role', 'button', 'Currency'),
        'button:has-text("Currency")',
        'button:has-text("Currencies")',
        '[data-name*="currency"]',
    ], timeout=1500)
    await asyncio.sleep(0.3)

    for curr in ["USD", "CAD"]:
        ok = (
            await safe_check(page, [
                ('role', 'checkbox', curr),
                f'label:has-text("{curr}")'
            ], timeout=1500)
            or await safe_click(page, [
                f'button:has-text("{curr}")',
                f'[aria-label*="{curr}"]',
                f'div:has-text("{curr}")'
            ], timeout=1500)
        )
        if not ok:
            print(f"[TV][WARN] Could not select currency: {curr}")

    # Apply / close filters if there’s an explicit button
    await safe_click(page, [
        'button:has-text("Apply")',
        ('role', 'button', 'Apply'),
        'button:has-text("Done")',
        ('role', 'button', 'Done'),
        'button:has-text("Close")'
    ], timeout=1500)
    await asyncio.sleep(2)

    # Try to target the calendar list/table container to screenshot
    print("[TV] Capturing screenshot…")
    saved = False
    for sel in [
        'section:has(table)',        # generic section wrapping a table
        'div:has(table)',
        'main',
        '#root',
    ]:
        try:
            el = await page.query_selector(sel)
            if el:
                await el.screenshot(path=TV_CAL_PNG)
                saved = True
                break
        except:
            pass

    if not saved:
        await page.screenshot(path=TV_CAL_PNG, full_page=True)

    print(f"[TV][OK] Saved: {TV_CAL_PNG}")
    await page.close()
    return True

async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            viewport={'width': 1600, 'height': 1600},
            user_agent=("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                        "AppleWebKit/537.36 (KHTML, like Gecko) "
                        "Chrome/120.0.0.0 Safari/537.36")
        )

        # 1) Pinned tweet (earnings)
        await capture_pinned_tweet(context)

        # 2) TradingView calendar (This week, High, USD + CAD)
        await capture_tradingview_calendar(context)

        await browser.close()

if __name__ == "__main__":
    asyncio.run(main())
