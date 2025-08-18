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
    Only uses https://www.tradingview.com/economic-calendar/
    """
    url = "https://www.tradingview.com/economic-calendar/"
    page = await context.new_page()
    print(f"[TV] Navigating… {url}")
    await page.goto(url)
    await asyncio.sleep(6)

    # Verify we’re on the correct host/path (avoid “bad page” captures)
    try:
        loc = page.url
        if not (loc.startswith("https://www.tradingview.com/economic-calendar/")):
            print(f"[TV][WARN] Unexpected location: {loc}")
            await page.close()
            return False
    except:
        pass

    # Accept cookies if shown (best-effort)
    for sel in [
        'button:has-text("Accept all")',
        'button:has-text("Accept All")',
        'button:has-text("I accept")',
        'button:has-text("Agree")',
        ('role', 'button', 'Accept'),
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

    # Open filters/settings if necessary
    print("[TV] Opening filters/settings…")
    for sel in [
        ('role', 'button', 'Filter'),
        'button:has-text("Filter")',
        'button:has-text("Filters")',
        'button[aria-label*="Filter"]',
        'button[title*="Filter"]'
    ]:
        try:
            if isinstance(sel, tuple):
                _, role, name = sel
                await page.get_by_role(role, name=name).click(timeout=2000)
            else:
                await page.locator(sel).first.click(timeout=2000)
            await asyncio.sleep(0.5)
            break
        except:
            continue

    # Date range: This week
    print("[TV] Setting date range: This week…")
    try:
        # Open date dropdown if present
        for sel in [
            ('role', 'button', 'Date'),
            'button:has-text("Date")',
            'button[aria-label*="Date"]',
            '[data-name*="date"]'
        ]:
            try:
                if isinstance(sel, tuple):
                    _, role, name = sel
                    await page.get_by_role(role, name=name).click(timeout=1500)
                else:
                    await page.locator(sel).first.click(timeout=1500)
                await asyncio.sleep(0.3)
                break
            except:
                pass

        # Pick "This week"
        for sel in [
            ('role', 'option', 'This week'),
            'div[role="option"]:has-text("This week")',
            'li:has-text("This week")',
            'button:has-text("This week")'
        ]:
            try:
                if isinstance(sel, tuple):
                    _, role, name = sel
                    await page.get_by_role(role, name=name).click(timeout=1500)
                else:
                    await page.locator(sel).first.click(timeout=1500)
                await asyncio.sleep(0.3)
                break
            except:
                pass
    except:
        print("[TV][WARN] Could not set date range explicitly.")

    # Importance: High only
    print("[TV] Selecting Impact: High…")
    try:
        for opener in [
            ('role', 'button', 'Importance'),
            'button:has-text("Importance")',
            '[data-name*="importance"]'
        ]:
            try:
                if isinstance(opener, tuple):
                    _, role, name = opener
                    await page.get_by_role(role, name=name).click(timeout=1500)
                else:
                    await page.locator(opener).first.click(timeout=1500)
                await asyncio.sleep(0.2)
                break
            except:
                pass

        for high in [
            ('role', 'checkbox', 'High'),
            'label:has-text("High")',
            'button:has-text("High")',
            '[aria-label*="High"]'
        ]:
            try:
                if isinstance(high, tuple):
                    _, role, name = high
                    await page.get_by_role(role, name=name).check(timeout=1500)
                else:
                    # If it's a button/label chip
                    try:
                        await page.locator(high).first.check(timeout=1200)
                    except:
                        await page.locator(high).first.click(timeout=1200)
                await asyncio.sleep(0.2)
                break
            except:
                pass
    except:
        print("[TV][WARN] Could not confirm High selection.")

    # Currencies: USD + CAD
    print("[TV] Selecting currencies: USD + CAD…")
    try:
        for opener in [
            ('role', 'button', 'Currency'),
            'button:has-text("Currency")',
            'button:has-text("Currencies")',
            '[data-name*="currency"]'
        ]:
            try:
                if isinstance(opener, tuple):
                    _, role, name = opener
                    await page.get_by_role(role, name=name).click(timeout=1500)
                else:
                    await page.locator(opener).first.click(timeout=1500)
                await asyncio.sleep(0.2)
                break
            except:
                pass

        for curr in ["USD", "CAD"]:
            done = False
            # Try checkbox first
            try:
                await page.get_by_role("checkbox", name=curr).check(timeout=1200)
                done = True
            except:
                pass
            if not done:
                for sel in [
                    f'label:has-text("{curr}")',
                    f'button:has-text("{curr}")',
                    f'[aria-label*="{curr}"]',
                    f'div:has-text("{curr}")'
                ]:
                    try:
                        await page.locator(sel).first.click(timeout=1200)
                        done = True
                        break
                    except:
                        continue
            if not done:
                print(f"[TV][WARN] Could not select currency: {curr}")
    except:
        print("[TV][WARN] Currency selection skipped.")

    # Apply / close filters, if there’s an explicit button
    for sel in [
        'button:has-text("Apply")',
        ('role', 'button', 'Apply'),
        'button:has-text("Done")',
        ('role', 'button', 'Done'),
        'button:has-text("Close")'
    ]:
        try:
            if isinstance(sel, tuple):
                _, role, name = sel
                await page.get_by_role(role, name=name).click(timeout=1200)
            else:
                await page.locator(sel).first.click(timeout=1200)
            await asyncio.sleep(0.5)
            break
        except:
            continue

    # Make sure the calendar content exists before saving
    print("[TV] Capturing screenshot…")
    container = None
    for sel in [
        'section:has(table)',
        'div:has(table)',
        'main',
        '#root'
    ]:
        try:
            el = await page.query_selector(sel)
            if el:
                container = el
                break
        except:
            pass

    if not container:
        print("[TV][WARN] Calendar container not found; skipping image to avoid bad post.")
        await page.close()
        return False

    await container.screenshot(path=TV_CAL_PNG)
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

