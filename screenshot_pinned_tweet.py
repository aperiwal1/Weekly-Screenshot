import asyncio
import os
import math
from playwright.async_api import async_playwright

OUTPUT_DIR = "site"
os.makedirs(OUTPUT_DIR, exist_ok=True)

PINNED_TWEET_PNG = os.path.join(OUTPUT_DIR, "pinned_tweet.png")
# Keep filename so your workflow & Slack step don't need changes:
FXS_CAL_PNG      = os.path.join(OUTPUT_DIR, "fxstreet_usd_cad_high.png")

# ---------- helpers ----------

async def safe_click(page, selectors, timeout=3000):
    """Try a list of selectors until one clicks; supports ('role','button','Name') tuples."""
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

# ---------- captures ----------

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

# ---------- Myfxbook calendar (but keep same filename) ----------

async def capture_fxstreet_calendar(context):
    """
    Myfxbook Economic Calendar (keeping output name for workflow compatibility):
      - Date: This Week
      - Impact: High only
      - Currencies: USD + CAD
      - Auto-scroll to load late-week items, then crop the top portion
    """
    url = "https://www.myfxbook.com/forex-economic-calendar"
    page = await context.new_page()
    print(f"[MFB] Navigating… {url}")
    await page.goto(url)
    await asyncio.sleep(6)

    # Accept cookies if shown
    for sel in [
        'button:has-text("Accept")',
        'button:has-text("I Accept")',
        'button:has-text("Agree")',
        ('role', 'button', 'Accept'),
        '[aria-label*="accept"]'
    ]:
        if await safe_click(page, [sel], timeout=1500):
            await asyncio.sleep(1)
            break

    # 1) Click "This Week"
    print("[MFB] Selecting 'This Week'…")
    week_ok = await safe_click(page, [
        'button:has-text("This Week")',
        ('role', 'button', 'This Week'),
        'a:has-text("This Week")'
    ], timeout=4000)
    if not week_ok:
        # Some UIs show "Week" or a calendar range dropdown
        week_ok = await safe_click(page, [
            'button:has-text("Week")',
            ('role', 'button', 'Week')
        ], timeout=2000)
    if not week_ok:
        print("[MFB][WARN] Could not confirm 'This Week' selection; proceeding.")

    await asyncio.sleep(2)

    # 2) Impact: High only (uncheck Medium/Low)
    print("[MFB] Setting Impact: High only…")
    # Open importance/impact controls if collapsed
    await safe_click(page, [
        'button:has-text("Importance")',
        ('role', 'button', 'Importance'),
        '[aria-label*="Importance"]',
        '[data-testid*="importance"]'
    ], timeout=1500)

    # Uncheck Medium/Low if on
    for low in ["Low", "Medium"]:
        await safe_click(page, [
            ('role', 'checkbox', low),
            f'label:has-text("{low}")',
            f'input[type="checkbox"][value*="{low.lower()}"]',
            f'button:has-text("{low}")'
        ], timeout=800)

    # Ensure High is selected
    await safe_check(page, [
        ('role', 'checkbox', 'High'),
        'label:has-text("High")',
        'input[type="checkbox"][value*="high"]',
        'button:has-text("High")',
        '[aria-label*="High"]'
    ], timeout=1500)

    # 3) Currencies: USD + CAD
    print("[MFB] Selecting currencies: USD + CAD…")
    # Open currency filter if needed
    await safe_click(page, [
        'button:has-text("Currency")',
        'button:has-text("Currencies")',
        ('role', 'button', 'Currency'),
        '[aria-label*="Currency"]',
        '[data-testid*="currency"]'
    ], timeout=1500)
    await asyncio.sleep(0.4)

    # Deselect all (if there is a clear/reset)
    await safe_click(page, [
        'button:has-text("Clear")',
        'button:has-text("Reset")',
        'a:has-text("Clear")',
        'a:has-text("Reset")'
    ], timeout=1000)

    # Now select only USD and CAD
    for curr in ["USD", "CAD"]:
        ok = await safe_check(page, [
            ('role', 'checkbox', curr),
            f'label:has-text("{curr}")',
            f'input[type="checkbox"][value="{curr}"]',
            f'button:has-text("{curr}")',
            f'[aria-label*="{curr}"]'
        ], timeout=1500)
        if not ok:
            print(f"[MFB][WARN] Could not select currency: {curr}")

    # Apply/close filters if an explicit button exists
    await safe_click(page, [
        'button:has-text("Apply")',
        ('role', 'button', 'Apply'),
        'button:has-text("Done")',
        ('role', 'button', 'Done'),
        'button:has-text("Close")',
        'button:has-text("OK")'
    ], timeout=1500)

    await asyncio.sleep(2)

    # 4) Ensure full week is loaded (lazy loading)
    await _mfb_load_full_week(page)

    # 5) Crop a compact top section
    await capture_myfxbook_container(page, crop_height=1200)
    await page.close()
    return True

async def _mfb_load_full_week(page):
    """Scrolls the list to trigger lazy-loading until Thu/Fri appears, then back to top."""
    print("[MFB] Ensuring full week is loaded…")
    await page.evaluate("""
      (function() {
        const possibles = [
          'section:has(table)',
          'div:has(table)',
          '#economicCalendarTab',
          '.economicCalendar',
          '[data-testid*="calendar"]',
          'main'
        ];
        for (const sel of possibles) {
          const el = document.querySelector(sel);
          if (el) { window.__calEl = el; return true; }
        }
        window.__calEl = document.scrollingElement;
        return true;
      })();
    """)

    saw_late_week = False
    for _ in range(16):
        try:
            await page.evaluate("""
              (function() {
                const el = window.__calEl || document.scrollingElement;
                el.scrollBy({ top: window.innerHeight, left: 0, behavior: 'instant' });
              })();
            """)
        except:
            pass
        await asyncio.sleep(0.7)
        html = (await page.content())[:220000].lower()
        if any(day in html for day in ["thu", "fri", "sat", "sun"]):
            saw_late_week = True
            break

    # Back to top for a clean crop
    try:
        await page.evaluate("""
          (function() {
            const el = window.__calEl || document.scrollingElement;
            el.scrollTo({ top: 0, left: 0, behavior: 'instant' });
          })();
        """)
    except:
        pass
    await asyncio.sleep(0.6)
    print(f"[MFB] Late-week detected: {saw_late_week}")

async def capture_myfxbook_container(page, crop_height=1200):
    """
    Screenshot the calendar container (preferred) or top-cropped full page.
    Saves to FXS_CAL_PNG to keep workflow unchanged.
    """
    print("[MFB] Capturing calendar area…")
    container = None
    for sel in [
        '#economicCalendarTab',
        '.economicCalendar',
        'section:has(table)',
        'div:has(table)',
        '[data-testid*="calendar"]',
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
        # fallback: crop top of viewport
        if crop_height:
            clip = {"x": 0, "y": 0, "width": 1600, "height": crop_height}
            await page.screenshot(path=FXS_CAL_PNG, clip=clip)
        else:
            await page.screenshot(path=FXS_CAL_PNG, full_page=True)
        print(f"[MFB][OK] Saved (fallback): {FXS_CAL_PNG}")
        return

    box = await container.bounding_box()
    if not box:
        await page.screenshot(path=FXS_CAL_PNG, full_page=True)
        print(f"[MFB][OK] Saved (bbox fallback): {FXS_CAL_PNG}")
        return

    top_height = crop_height if crop_height else box["height"]
    clip = {
        "x": int(box["x"]),
        "y": int(box["y"]),
        "width": int(box["width"]),
        "height": int(min(box["height"], top_height))
    }
    await page.screenshot(path=FXS_CAL_PNG, clip=clip)
    print(f"[MFB][OK] Saved (cropped): {FXS_CAL_PNG}")

# ---------- main ----------

async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            viewport={'width': 1600, 'height': 1600},
            user_agent=("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                        "AppleWebKit/537.36 (KHTML, like Gecko) "
                        "Chrome/120.0.0.0 Safari/537.36")
        )

        await capture_pinned_tweet(context)
        await capture_fxstreet_calendar(context)  # now points to Myfxbook

        await browser.close()

if __name__ == "__main__":
    asyncio.run(main())
