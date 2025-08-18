import asyncio
import os
import math
from playwright.async_api import async_playwright

OUTPUT_DIR = "site"
os.makedirs(OUTPUT_DIR, exist_ok=True)

PINNED_TWEET_PNG = os.path.join(OUTPUT_DIR, "pinned_tweet.png")
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
    for sel in selectors:
        try:
            if isinstance(sel, tuple) and len(sel) == 3 and sel[0] == "role":
                _, role, name = sel
                await page.get_by_role(role, name=name).check(timeout=timeout)
            else:
                await page.locator(sel).first.check(timeout=timeout)
            return True
        except:
            # If the element is a chip/button rather than a checkbox, try clicking
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

async def capture_fxstreet_calendar(context):
    """
    FXStreet Economic Calendar:
      - Click top 'This Week' chip to force full-week view
      - Open Filter panel and set: Impact=High, Countries=United States + Canada
      - Auto-scroll to load late-week items (Thu/Fri)
      - Crop the top portion for a concise snip
    """
    url = "https://www.fxstreet.com/economic-calendar"
    page = await context.new_page()
    print(f"[FXS] Navigating… {url}")
    await page.goto(url)
    await asyncio.sleep(6)

    # Sanity: correct domain
    if "fxstreet.com/economic-calendar" not in page.url:
        print(f"[FXS][WARN] Unexpected URL after navigation: {page.url}")

    # Accept cookies if shown
    for sel in [
        'button:has-text("Accept all")',
        'button:has-text("Accept All")',
        ('role', 'button', 'Accept'),
        'button:has-text("Agree")',
        'button[aria-label*="Accept"]'
    ]:
        if await safe_click(page, [sel], timeout=1500):
            await asyncio.sleep(1)
            break

    # 1) Force "This Week" from the header chips (robust against local cache)
    print("[FXS] Forcing 'This Week' view from header…")
    forced_week = await safe_click(page, [
        'button:has-text("This week")',
        ('role', 'button', 'This week'),
        'a:has-text("This week")'
    ], timeout=4000)
    if not forced_week:
        print("[FXS][WARN] Could not click header 'This week' chip.")
    await asyncio.sleep(2)

    # 2) Open Filter panel
    print("[FXS] Opening Filter panel…")
    opened = await safe_click(page, [
        ('role', 'button', 'Filter'),
        'button:has-text("Filter")',
        'button[aria-label*="Filter"]',
        'button:has-text("Filters")',
    ], timeout=3000)
    if not opened:
        print("[FXS][WARN] Could not open Filter panel; will capture with header week only.")
        # Ensure full-week content is loaded before screenshot
        await _fxs_load_full_week(page)
        await capture_fxstreet_container(page, crop_height=1200)
        await page.close()
        return True
    await asyncio.sleep(0.6)

    # 3) Impact = High only (unselect Low/Medium if toggled)
    print("[FXS] Selecting Impact: High…")
    await safe_click(page, [
        ('role', 'button', 'Impact'),
        'button:has-text("Impact")',
        '[data-testid*="impact"]',
    ], timeout=1500)
    await asyncio.sleep(0.2)
    for low in ["Low", "Medium"]:
        await safe_click(page, [
            ('role', 'checkbox', low),
            f'label:has-text("{low}")',
            f'button:has-text("{low}")'
        ], timeout=800)  # toggles off if on
    await safe_check(page, [
        ('role', 'checkbox', 'High'),
        'label:has-text("High")',
        'button:has-text("High")',
        '[aria-label*="High"]'
    ], timeout=1500)

    # 4) Countries = United States + Canada
    print("[FXS] Selecting Countries: United States + Canada…")
    await safe_click(page, [
        ('role', 'button', 'Country'),
        'button:has-text("Country")',
        'button:has-text("Countries")',
        '[data-testid*="country"]',
    ], timeout=1500)
    await asyncio.sleep(0.2)
    # Clear any preselect
    await safe_click(page, [
        'button:has-text("Clear")',
        'button:has-text("Clear all")',
        'button:has-text("Reset")',
    ], timeout=800)

    for name in ["United States", "Canada"]:
        ok = await safe_check(page, [
            ('role', 'checkbox', name),
            f'label:has-text("{name}")',
            f'button:has-text("{name}")',
            f'[aria-label*="{name}"]',
        ], timeout=1500)
        if not ok:
            print(f"[FXS][WARN] Could not select country: {name}")

    # Apply filters
    print("[FXS] Applying filters…")
    await safe_click(page, [
        'button:has-text("Apply")',
        ('role', 'button', 'Apply'),
        'button:has-text("Done")',
        ('role', 'button', 'Done'),
        'button:has-text("Close")'
    ], timeout=2000)
    await asyncio.sleep(2)

    # 5) Ensure full week is loaded (lazy-loaded list)
    await _fxs_load_full_week(page)

    # 6) Crop top portion for compact snip
    await capture_fxstreet_container(page, crop_height=1200)
    await page.close()
    return True


async def _fxs_load_full_week(page):
    """Scrolls the calendar to trigger lazy-loading until Thu/Fri appear, then back to top."""
    print("[FXS] Ensuring full week is loaded…")
    # Find scrollable calendar container if any; else use page
    await page.evaluate("""
      (function() {
        const el =
          document.querySelector('section:has(table)') ||
          document.querySelector('div:has(table)') ||
          document.querySelector('[data-testid*="calendar"]') ||
          document.querySelector('main') ||
          document.scrollingElement;
        window.__calEl = el || document.scrollingElement;
        return true;
      })();
    """)

    saw_late_week = false_detected = False
    for _ in range(16):  # up to ~16 screens
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
        # Look for late-week day labels in the HTML chunk
        html = (await page.content())[:220000].lower()
        if any(day in html for day in ["thu", "fri", "sat", "sun"]):
            saw_late_week = True
            break

    # Scroll back to top for clean capture
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
    print(f"[FXS] Late-week detected: {saw_late_week}")


async def capture_fxstreet_container(page, crop_height=1200):
    """
    Screenshot the calendar container (preferred) or a top-cropped full-page fallback.
    """
    print("[FXS] Capturing calendar area…")
    container = None
    for sel in [
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

    target_path = os.path.join(OUTPUT_DIR, "fxstreet_usd_cad_high.png")

    if not container:
        # fallback: crop the top of the viewport
        if crop_height:
            clip = {"x": 0, "y": 0, "width": 1600, "height": crop_height}
            await page.screenshot(path=target_path, clip=clip)
        else:
            await page.screenshot(path=target_path, full_page=True)
        print(f"[FXS][OK] Saved (fallback): {target_path}")
        return

    box = await container.bounding_box()
    if not box:
        await page.screenshot(path=target_path, full_page=True)
        print(f"[FXS][OK] Saved (bbox fallback): {target_path}")
        return

    top_height = crop_height if crop_height else box["height"]
    clip = {
        "x": int(box["x"]),
        "y": int(box["y"]),
        "width": int(box["width"]),
        "height": int(min(box["height"], top_height))
    }
    await page.screenshot(path=target_path, clip=clip)
    print(f"[FXS][OK] Saved (cropped): {target_path}")


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
        await capture_fxstreet_calendar(context)

        await browser.close()

if __name__ == "__main__":
    asyncio.run(main())



