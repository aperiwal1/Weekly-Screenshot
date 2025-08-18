import asyncio
import os
from pathlib import Path
from playwright.async_api import async_playwright

OUTPUT_DIR = Path("site")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

PINNED_TWEET_PNG = OUTPUT_DIR / "pinned_tweet.png"
WIDGET_HTML      = OUTPUT_DIR / "fxs_widget.html"
ECON_PNG         = OUTPUT_DIR / "econ_us_ca_high.png"

# ----------------- helpers -----------------

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
    """Try to check a checkbox-like thing; if not checkable, click it."""
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
    """Scroll to trigger lazy-load until late-week markers appear, then back to top."""
    await page.evaluate("""
      (function(){
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
              (function(){
                const el = window.__calEl || document.scrollingElement;
                el.scrollBy({ top: window.innerHeight, left: 0, behavior: 'instant' });
              })();
            """)
        except:
            pass
        await asyncio.sleep(0.7)
        html = (await page.content())[:240000].lower()
        if any(d.lower() in html for d in late_day_markers):
            saw_late = True
            break
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
    await asyncio.sleep(0.6)
    print(f"[Widget] Late-week detected: {saw_late}")

async def crop_container_or_top(page, out_path, crop_height=1200):
    """Crop the main calendar/container or top of viewport."""
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
        await page.screenshot(path=str(out_path), clip=clip)
        print(f"[Widget][OK] Saved (fallback top-crop): {out_path}")
        return

    box = await container.bounding_box()
    if not box:
        await page.screenshot(path=str(out_path), full_page=True)
        print(f"[Widget][OK] Saved (bbox fallback): {out_path}")
        return

    top_height = int(min(box["height"], crop_height))
    clip = {
        "x": int(box["x"]),
        "y": int(box["y"]),
        "width": int(box["width"]),
        "height": top_height
    }
    await page.screenshot(path=str(out_path), clip=clip)
    print(f"[Widget][OK] Saved (cropped): {out_path}")

# ----------------- captures -----------------

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

    await tweet.screenshot(path=str(PINNED_TWEET_PNG))
    print(f"[Pinned][OK] Saved: {PINNED_TWEET_PNG}")
    await page.close()
    return True

def write_widget_html():
    """
    Generates a minimal HTML that embeds the FXStreet Calendar widget.
    We set:
      - country-code="US,CA"
      - timezone-offset="240"  (Toronto in August is UTC-4 → +240 minutes behind UTC)
    Impact + Date (This Week) are selected via scripted clicks after load.
    Docs: calendar widget parameters + utilities. 
    """
    WIDGET_HTML.write_text(f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <title>FXStreet Calendar — US & CA</title>
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <!-- FXStreet widget loader -->
  <script src="https://staticcontent.fxsstatic.com/widgets-v2/stable/fxs-widgets.js" defer></script>
  <style>
    body {{ margin: 0; font-family: system-ui, -apple-system, Segoe UI, Roboto, sans-serif; }}
    .wrap {{ max-width: 1600px; margin: 0 auto; padding: 12px; }}
    h1 {{ font-size: 18px; margin: 8px 0 12px; }}
    .calendar {{ border: 1px solid #e5e7eb; border-radius: 10px; overflow: hidden; }}
  </style>
</head>
<body>
  <div class="wrap">
    <h1>High-Impact US & Canada — This Week</h1>
    <!-- FXStreet Economic Calendar widget -->
    <div class="calendar">
      <div
        fxs-widget
        name="calendar"
        country-code="US,CA"
        timezone-offset="240">
      </div>
    </div>
  </div>
</body>
</html>
""", encoding="utf-8")
    print(f"[Widget] Wrote {WIDGET_HTML}")

async def capture_fxstreet_widget(context):
    # 1) write local HTML with widget
    write_widget_html()

    # 2) open the local file
    file_url = WIDGET_HTML.resolve().as_uri()  # file:///...
    page = await context.new_page()
    print(f"[Widget] Opening local widget page… {file_url}")
    await page.goto(file_url)
    # wait extra for widget JS to load and render
    await asyncio.sleep(6)

    # 3) Try to click "This Week" in the widget’s own UI
    print("[Widget] Forcing 'This Week'…")
    await safe_click(page, [
        'button:has-text("This Week")',
        ('role', 'button', 'This Week'),
        'a:has-text("This Week")',
        'button:has-text("Week")'
    ], timeout=4000)
    await asyncio.sleep(1.5)

    # 4) Impact: High only (unselect Low/Medium if toggled)
    print("[Widget] Selecting High impact…")
    # Open impact/importance control if needed
    await safe_click(page, [
        'button:has-text("Impact")',
        ('role', 'button', 'Impact'),
        '[aria-label*="Impact"]',
        '[data-testid*="impact"]',
        'button:has-text("Importance")',
        ('role', 'button', 'Importance'),
    ], timeout=2000)
    await asyncio.sleep(0.4)
    # Unselect lower levels
    for low in ["Low", "Medium"]:
        await safe_click(page, [
            ('role', 'checkbox', low),
            f'label:has-text("{low}")',
            f'button:has-text("{low}")',
            f'[aria-label*="{low}"]'
        ], timeout=900)
    # Ensure High is on
    await safe_check(page, [
        ('role', 'checkbox', 'High'),
        'label:has-text("High")',
        'button:has-text("High")',
        '[aria-label*="High"]',
        'span:has-text("★★★")'
    ], timeout=1500)
    # Apply/close if present
    await safe_click(page, [
        'button:has-text("Apply")',
        ('role', 'button', 'Apply'),
        'button:has-text("Done")',
        ('role', 'button', 'Done'),
        'button:has-text("Close")',
        'button:has-text("OK")'
    ], timeout=1500)

    # 5) Scroll to load late week, then back to top; crop compact section
    await scroll_load_full_week(page)
    await crop_container_or_top(page, ECON_PNG, crop_height=1200)
    await page.close()
    return True

# ----------------- main -----------------

async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            viewport={'width': 1600, 'height': 1600},
            user_agent=("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                        "AppleWebKit/537.36 (KHTML, like Gecko) "
                        "Chrome/120.0.0.0 Safari/537.36")
        )

        # Earnings (pinned tweet) – in Slack we’ll title it “Earnings Calendar”
        await capture_pinned_tweet(context)

        # FXStreet widget (US+CA), forced to This Week + High via clicks
        await capture_fxstreet_widget(context)

        await browser.close()

if __name__ == "__main__":
    asyncio.run(main())
