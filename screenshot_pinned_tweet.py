import asyncio
import os
from playwright.async_api import async_playwright

OUTPUT_DIR = "site"
os.makedirs(OUTPUT_DIR, exist_ok=True)

PINNED_TWEET_PNG = os.path.join(OUTPUT_DIR, "pinned_tweet.png")
TE_US_PNG        = os.path.join(OUTPUT_DIR, "te_us_high.png")
TE_CA_PNG        = os.path.join(OUTPUT_DIR, "te_ca_high.png")

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

async def scroll_load_full_week(page, late_day_markers=("Thu","Fri","Sat","Sun"), max_steps=16):
    """Scroll container/page to trigger lazy-load until late-week markers appear, then back to top."""
    await page.evaluate("""
      (function() {
        // grab a sensible scrollable container if present
        const candidates = [
          'section:has(table)',
          'div:has(table)',
          '[data-testid*="calendar"]',
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
    saw_late = False
    for _ in range(max_steps):
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
        if any(d.lower() in html for d in late_day_markers):
            saw_late = True
            break
    # back to top
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
    print(f"[TE] Late-week detected: {saw_late}")

async def crop_container_or_top(page, out_path, crop_height=1200):
    """Crop the main calendar/container or, if not found, top of viewport."""
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
        clip = {"x": 0, "y": 0, "width": 1600, "height": crop_height}
        await page.screenshot(path=out_path, clip=clip)
        print(f"[TE][OK] Saved (fallback top-crop): {out_path}")
        return

    box = await container.bounding_box()
    if not box:
        await page.screenshot(path=out_path, full_page=True)
        print(f"[TE][OK] Saved (bbox fallback): {out_path}")
        return

    top_height = int(min(box["height"], crop_height))
    clip = {
        "x": int(box["x"]),
        "y": int(box["y"]),
        "width": int(box["width"]),
        "height": top_height
    }
    await page.screenshot(path=out_path, clip=clip)
    print(f"[TE][OK] Saved (cropped): {out_path}")

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

async def capture_te_country_calendar(context, country_slug, out_path):
    """
    TradingEconomics country calendar:
      - Force 'This Week'
      - Set importance=High (3-star)
      - Scroll to load full week
      - Crop top portion
    """
    url = f"https://tradingeconomics.com/{country_slug}/calendar"
    page = await context.new_page()
    print(f"[TE] Navigating… {url}")
    await page.goto(url)
    await asyncio.sleep(6)

    # Accept cookies if shown (best effort)
    for sel in [
        'button:has-text("Accept")',
        'button:has-text("I Accept")',
        'button:has-text("Agree")',
        'button:has-text("Accept All")',
        ('role', 'button', 'Accept'),
        '[aria-label*="accept"]'
    ]:
        if await safe_click(page, [sel], timeout=1500):
            await asyncio.sleep(1)
            break

    # 1) Date: This Week (header chip or menu option)
    print("[TE] Selecting This Week…")
    week_ok = await safe_click(page, [
        'button:has-text("This Week")',
        ('role', 'button', 'This Week'),
        'a:has-text("This Week")',
        'li:has-text("This Week")',
        'div[role="option"]:has-text("This Week")',
        'button:has-text("Week")'  # fallback
    ], timeout=4000)
    if not week_ok:
        print("[TE][WARN] Could not confirm 'This Week' selection.")
    await asyncio.sleep(2)

    # 2) Importance: High / 3-star
    print("[TE] Selecting High importance…")
    # Try to open an importance filter if it exists
    await safe_click(page, [
        'button:has-text("Importance")',
        ('role', 'button', 'Importance'),
        '[aria-label*="Importance"]',
        '[data-testid*="importance"]',
        'button:has-text("Priority")',
        ('role', 'button', 'Priority')
    ], timeout=1500)
    await asyncio.sleep(0.2)

    # Unselect lower levels
    for low in ["Low", "Medium"]:
        await safe_click(page, [
            ('role', 'checkbox', low),
            f'label:has-text("{low}")',
            f'button:has-text("{low}")',
            f'[aria-label*="{low}"]'
        ], timeout=800)

    # Ensure High is on
    high_ok = await safe_check(page, [
        ('role', 'checkbox', 'High'),
        'label:has-text("High")',
        'button:has-text("High")',
        '[aria-label*="High"]',
        'span:has-text("★★★")',   # star marker fallback
    ], timeout=1500)
    if not high_ok:
        print("[TE][WARN] Could not confirm High selection.")

    # Apply/close if there is an explicit button
    await safe_click(page, [
        'button:has-text("Apply")',
        ('role', 'button', 'Apply'),
        'button:has-text("Done")',
        ('role', 'button', 'Done'),
        'button:has-text("Close")'
    ], timeout=1500)

    await asyncio.sleep(2)

    # 3) Ensure full week is loaded
    await scroll_load_full_week(page)

    # 4) Crop compact top section
    await crop_container_or_top(page, out_path, crop_height=1200)
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

        # Earnings (pinned tweet) – title will be “Earnings Calendar” in Slack
        await capture_pinned_tweet(context)

        # US (High, This Week)
        await capture_te_country_calendar(context, "united-states", TE_US_PNG)

        # Canada (High, This Week)
        await capture_te_country_calendar(context, "canada", TE_CA_PNG)

        await browser.close()

if __name__ == "__main__":
    asyncio.run(main())
