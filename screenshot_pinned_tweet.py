import asyncio
import os
from playwright.async_api import async_playwright

OUTPUT_DIR = "site"
os.makedirs(OUTPUT_DIR, exist_ok=True)

PINNED_TWEET_PNG = os.path.join(OUTPUT_DIR, "pinned_tweet.png")
FF_CAL_PNG       = os.path.join(OUTPUT_DIR, "forexfactory_usd_cad_high.png")

# ---------------- helpers ----------------

async def safe_click(page, selectors, timeout=3000):
    """Try selectors until one clicks; supports ('role','button','Name') tuples."""
    for sel in selectors:
        try:
            if isinstance(sel, tuple) and len(sel) == 3 and sel[0] == "role":
                _, role, name = sel
                await page.get_by_role(role, name=name).click(timeout=timeout)
            else:
                await page.locator(sel).first.click(timeout=timeout)
            return True
        except:
            continue
    return False

async def safe_check(page, selectors, timeout=3000):
    """Try to .check() a checkbox-like control; if that fails, click it."""
    for sel in selectors:
        try:
            if isinstance(sel, tuple) and len(sel) == 3 and sel[0] == "role":
                _, role, name = sel
                await page.get_by_role(role, name=name).check(timeout=timeout)
                return True
            else:
                await page.locator(sel).first.check(timeout=timeout)
                return True
        except:
            try:
                if not (isinstance(sel, tuple) and sel[0] == "role"):
                    await page.locator(sel).first.click(timeout=timeout)
                    return True
            except:
                continue
    return False

async def crop_container_or_top(page, out_path, crop_height=2000):
    """Crop the main calendar/container or, if not found, top of viewport."""
    container = None
    for sel in [
        'div.calendar__table',    # try new FF calendar table
        '#calendars',             # older container id
        '.calendar',              # generic
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
        clip = {"x": 0, "y": 0, "width": 1600, "height": crop_height}
        await page.screenshot(path=out_path, clip=clip)
        print(f"[FF][OK] Saved (fallback top-crop): {out_path}")
        return

    box = await container.bounding_box()
    if not box:
        await page.screenshot(path=out_path, full_page=True)
        print(f"[FF][OK] Saved (bbox fallback): {out_path}")
        return

    top_height = int(min(box["height"], crop_height))
    clip = {
        "x": int(box["x"]),
        "y": int(box["y"]),
        "width": int(box["width"]),
        "height": top_height
    }
    await page.screenshot(path=out_path, clip=clip)
    print(f"[FF][OK] Saved (cropped): {out_path}")

async def scroll_load_full_week(page, max_steps=14):
    """Scroll to trigger lazy-load, then back to top (best-effort)."""
    await page.evaluate("""
      (function(){
        const candidates = [
          'div.calendar__table',
          '#calendars',
          '.calendar',
          'main',
          '#root'
        ];
        for (const sel of candidates) {
          const el = document.querySelector(sel);
          if (el) { window.__calEl = el; return true; }
        }
        window.__calEl = document.scrollingElement;
        return true;
      })();
    """)
    for _ in range(max_steps):
        try:
            await page.evaluate("""
              (function(){
                const el = window.__calEl || document.scrollingElement;
                el.scrollBy({ top: window.innerHeight, left: 0, behavior: 'instant' });
              })();
            """)
        except:
            pass
        await asyncio.sleep(0.5)
    # back to top
    try:
        await page.evaluate("""
          (function(){
            const el = window.__calEl || document.scrollingElement;
            el.scrollTo({ top: 0, left: 0, behavior: 'instant' });
          })();
        """)
    except:
        pass
    await asyncio.sleep(0.5)

# ---------------- captures ----------------

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

async def capture_forexfactory_calendar(context):
    """
    ForexFactory Calendar (This Week). We TRY to set:
      - Impact: High
      - Currencies: USD + CAD
    But regardless of filter success, we ALWAYS save a screenshot
    so your Slack step never breaks.
    """
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
        if await safe_click(page, [sel], timeout=1500):
            await asyncio.sleep(1)
            break

    # Open filter panel
    print("[FF] Opening Filters…")
    opened = await safe_click(page, [
        ('role', 'button', 'Filter'),
        'button:has-text("Filter")',
        'button[aria-label*="Filter"]',
        'button[class*="filter"]'
    ], timeout=4000)

    if opened:
        await asyncio.sleep(0.6)

        # Clear All (if present)
        await safe_click(page, [
            'button:has-text("Clear All")',
            'text=Clear All'
        ], timeout=1200)
        await asyncio.sleep(0.3)

        # Currencies: USD + CAD
        print("[FF] Selecting currencies USD + CAD… (best-effort)")
        for curr in ["USD", "CAD"]:
            ok = (
                await safe_check(page, [
                    ('role', 'checkbox', curr),
                    f'label:has-text("{curr}")',
                    f'button:has-text("{curr}")',
                    f'[aria-label*="{curr}"]'
                ], timeout=1500)
            )
            if not ok:
                print(f"[FF][WARN] Could not confirm currency: {curr}")

        # Impact: High only
        print("[FF] Selecting Impact: High… (best-effort)")
        # Try to open impact section
        await safe_click(page, [
            ('role', 'button', 'Impact'),
            'button:has-text("Impact")',
            '[data-testid*="impact"]'
        ], timeout=1200)

        # Unselect Low/Medium if toggled
        for low in ["Low", "Medium"]:
            await safe_click(page, [
                ('role', 'checkbox', low),
                f'label:has-text("{low}")',
                f'button:has-text("{low}")'
            ], timeout=800)
        # Ensure High on
        await safe_check(page, [
            ('role', 'checkbox', 'High'),
            'label:has-text("High")',
            'button:has-text("High")',
            '[aria-label*="High"]'
        ], timeout=1500)

        # Apply
        await safe_click(page, [
            'button:has-text("Apply Filter")',
            'button:has-text("Apply")',
            ('role', 'button', 'Apply')
        ], timeout=1500)
        await asyncio.sleep(2)
    else:
        print("[FF][WARN] Could not open Filters; capturing default This Week view.")

    # Ensure content is loaded (scroll & back)
    await scroll_load_full_week(page)

    # Crop compact top section
    await crop_container_or_top(page, FF_CAL_PNG, crop_height=2000)
    await page.close()
    return True

# ---------------- main ----------------

async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            viewport={'width': 1600, 'height': 1600},
            user_agent=("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                        "AppleWebKit/537.36 (KHTML, like Gecko) "
                        "Chrome/120.0.0.0 Safari/537.36")
        )

        # 1) Earnings (pinned tweet)
        await capture_pinned_tweet(context)

        # 2) ForexFactory (This Week; best-effort filters)
        await capture_forexfactory_calendar(context)

        await browser.close()

if __name__ == "__main__":
    asyncio.run(main())


