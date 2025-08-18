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
    FXStreet Economic Calendar filters:
      - Date: This week
      - Countries: United States, Canada
      - Impact: High only
    Also: auto-scroll to load the full week, then crop the top portion.
    """
    url = "https://www.fxstreet.com/economic-calendar"
    page = await context.new_page()
    print(f"[FXS] Navigating… {url}")
    await page.goto(url)
    await asyncio.sleep(6)

    # quick sanity check to avoid bad/snapped pages
    if "fxstreet.com/economic-calendar" not in page.url:
        print(f"[FXS][WARN] Unexpected URL after navigation: {page.url}")

    # Accept cookies if shown (best-effort)
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

    # Open Filter panel
    print("[FXS] Opening Filter panel…")
    opened = await safe_click(page, [
        ('role', 'button', 'Filter'),
        'button:has-text("Filter")',
        'button[aria-label*="Filter"]',
        'button:has-text("Filters")',
    ], timeout=3000)
    if not opened:
        print("[FXS][WARN] Could not open Filter panel; capturing unfiltered view.")
        await capture_fxstreet_container(page, crop_height=1200)
        await page.close()
        return True
    await asyncio.sleep(0.6)

    # ---- Date range: This week ----
    print("[FXS] Setting Date: This week…")
    await safe_click(page, [
        ('role', 'button', 'Date'),
        'button:has-text("Date")',
        '[data-testid*="date"]',
        'button[aria-label*="Date"]'
    ], timeout=1500)
    await asyncio.sleep(0.3)
    set_week = await safe_click(page, [
        ('role', 'option', 'This week'),
        'div[role="option"]:has-text("This week")',
        'li:has-text("This week")',
        'button:has-text("This week")'
    ], timeout=2000)
    if not set_week:
        print("[FXS][WARN] Could not explicitly set 'This week'.")

    # ---- Impact: High only ----
    print("[FXS] Selecting Impact: High…")
    await safe_click(page, [
        ('role', 'button', 'Impact'),
        'button:has-text("Impact")',
        '[data-testid*="impact"]',
    ], timeout=1500)
    await asyncio.sleep(0.2)
    # Unselect lower impact if selected
    for low in ["Low", "Medium"]:
        await safe_click(page, [
            ('role', 'checkbox', low),
            f'label:has-text("{low}")',
            f'button:has-text("{low}")'
        ], timeout=800)
    # Ensure High is ON
    await safe_check(page, [
        ('role', 'checkbox', 'High'),
        'label:has-text("High")',
        'button:has-text("High")',
        '[aria-label*="High"]'
    ], timeout=1500)

    # ---- Countries: United States, Canada ----
    print("[FXS] Selecting Countries: United States + Canada…")
    await safe_click(page, [
        ('role', 'button', 'Country'),
        'button:has-text("Country")',
        'button:has-text("Countries")',
        '[data-testid*="country"]',
    ], timeout=1500)
    await asyncio.sleep(0.2)

    # Clear any preselected (best-effort)
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

    # ---- Ensure full week is loaded (lazy-load on scroll) ----
    print("[FXS] Ensuring full week is loaded…")
    # Scroll container (if exists) else scroll page
    scroll_script = """
      (function() {
        const el =
          document.querySelector('section:has(table)') ||
          document.querySelector('div:has(table)') ||
          document.querySelector('[data-testid*="calendar"]') ||
          document.querySelector('main') ||
          document.scrollingElement;
        let atBottom = false;
        window.__calEl = el;
        return !!el;
      })();
    """
    has_container = await page.evaluate(scroll_script)
    if not has_container:
        print("[FXS][WARN] Could not find calendar container; scrolling whole page.")
    # Scroll down in steps to load more, look for late-week markers
    saw_late_week = False
    for i in range(12):
        try:
            await page.evaluate("""
              (function() {
                const el = window.__calEl || document.scrollingElement;
                el.scrollBy({ top: window.innerHeight, behavior: 'instant' });
              })();
            """)
        except:
            pass
        await asyncio.sleep(0.7)

        # Heuristic: if we see Thu/Fri in viewport text, assume full week loaded
        text_snip = (await page.content())[:200000].lower()
        if any(day in text_snip for day in ["thu", "fri", "sat", "sun"]):
            saw_late_week = True
            break

    # Scroll back to top for a clean top crop
    try:
        await page.evaluate("""
          (function() {
            const el = window.__calEl || document.scrollingElement;
            el.scrollTo({ top: 0, behavior: 'instant' });
          })();
        """)
    except:
        pass
    await asyncio.sleep(0.6)

    # Capture the calendar area, cropped to top N pixels
    await capture_fxstreet_container(page, crop_height=1200)
    await page.close()
    return True

async def capture_fxstreet_container(page, crop_height=1200):
    """
    Screenshot the calendar container (preferred) or full page.
    If crop_height is provided, crop to the top part only.
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

    if not container:
        # fallback: full page crop from top
        if crop_height:
            clip = {"x": 0, "y": 0, "width": 1600, "height": crop_height}
            await page.screenshot(path=FXS_CAL_PNG, clip=clip)
        else:
            await page.screenshot(path=FXS_CAL_PNG, full_page=True)
        print(f"[FXS][OK] Saved (fallback): {FXS_CAL_PNG}")
        return

    # Use element bbox and crop to top N px
    box = await container.bounding_box()
    if not box:
        await page.screenshot(path=FXS_CAL_PNG, full_page=True)
        print(f"[FXS][OK] Saved (bbox fallback): {FXS_CAL_PNG}")
        return

    top_height = crop_height if crop_height else box["height"]
    clip = {
        "x": math.floor(box["x"]),
        "y": math.floor(box["y"]),
        "width": math.floor(box["width"]),
        "height": math.floor(min(box["height"], top_height))
    }
    await page.screenshot(path=FXS_CAL_PNG, clip=clip)
    print(f"[FXS][OK] Saved (cropped): {FXS_CAL_PNG}")

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


