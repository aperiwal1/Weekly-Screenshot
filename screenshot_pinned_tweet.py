import asyncio
import os
import json
import math
import requests
from datetime import datetime, timedelta
from playwright.async_api import async_playwright

OUTPUT_DIR = "site"
os.makedirs(OUTPUT_DIR, exist_ok=True)

PINNED_TWEET_PNG = os.path.join(OUTPUT_DIR, "pinned_tweet.png")
TE_CAL_PNG       = os.path.join(OUTPUT_DIR, "te_usd_cad_high.png")

def _monday_of_week(d):
    return d - timedelta(days=d.weekday())

def _sunday_of_week(d):
    return _monday_of_week(d) + timedelta(days=6)

def fetch_te_events_for_week(api_key: str):
    """United States + Canada, this week, importance=High."""
    today = datetime.utcnow().date()
    start = _monday_of_week(today)
    end   = _sunday_of_week(today)
    start_s = start.strftime("%Y-%m-%d")
    end_s   = end.strftime("%Y-%m-%d")

    # By country + importance + date range (see TE docs)
    countries = ["united%20states", "canada"]
    all_rows = []
    for ctry in countries:
        url = (
            f"https://api.tradingeconomics.com/calendar/country/{ctry}"
            f"/importance/high?d1={start_s}&d2={end_s}&c={api_key}"
        )
        r = requests.get(url, timeout=20)
        r.raise_for_status()
        data = r.json()
        if isinstance(data, dict) and "error" in data:
            raise RuntimeError(f"TE API error for {ctry}: {data['error']}")
        all_rows.extend(data)
    return all_rows, start_s, end_s

def html_for_events(events, start_s, end_s):
    # Normalize & sort by date/time
    def parse_dt(e):
        # TE fields often: 'DateUTC' or 'Date' + 'Time'
        # Try several keys safely.
        dt_s = e.get("DateUTC") or e.get("Date") or ""
        try:
            return datetime.fromisoformat(dt_s.replace("Z", "+00:00"))
        except Exception:
            return datetime.min

    events = sorted(events, key=parse_dt)

    # Build neat, print-friendly HTML (simple CSS)
    rows = []
    for e in events:
        country = e.get("Country", "")
        event   = e.get("Event", "") or e.get("Category", "")
        time    = e.get("DateUTC") or e.get("Date") or ""
        actual  = e.get("Actual", "")
        forecast= e.get("Forecast", "")
        previous= e.get("Previous", "")
        tznote  = "UTC"

        # Friendly time
        try:
            dt = datetime.fromisoformat(time.replace("Z", "+00:00"))
            time_disp = dt.strftime("%a %b %d, %H:%M")
        except:
            time_disp = time

        rows.append(f"""
          <tr>
            <td>{country}</td>
            <td>{time_disp} <span class="tz">{tznote}</span></td>
            <td>{event}</td>
            <td>{forecast}</td>
            <td>{previous}</td>
            <td>{actual}</td>
          </tr>
        """)

    empty_msg = ""
    if not rows:
        empty_msg = "<p class='empty'>No High-impact events for USD/CAD this week.</p>"

    html = f"""
<!doctype html>
<html>
<head>
<meta charset="utf-8" />
<title>High Impact: USD & CAD ({start_s} – {end_s})</title>
<style>
  body {{ font-family: Inter, system-ui, -apple-system, Segoe UI, Roboto, Arial, sans-serif; margin: 24px; }}
  h1 {{ font-size: 20px; margin: 0 0 4px; }}
  h2 {{ font-size: 13px; color: #666; margin: 0 0 16px; }}
  table {{ border-collapse: collapse; width: 100%; font-size: 13px; }}
  th, td {{ padding: 8px 10px; border-bottom: 1px solid #eaeaea; vertical-align: top; }}
  th {{ text-align: left; background: #fafafa; }}
  tr:nth-child(even) td {{ background: #fcfcfc; }}
  .tz {{ color: #999; font-size: 11px; margin-left: 4px; }}
  .empty {{ color: #999; font-style: italic; margin-top: 12px; }}
  .badge {{ display:inline-block; padding:2px 6px; font-size:11px; background:#fee; color:#b00; border:1px solid #f88; border-radius:8px; margin-left:6px; }}
  .foot {{ margin-top:10px; color:#999; font-size:11px; }}
</style>
</head>
<body>
  <h1>High-Impact Economic Events — USD & CAD</h1>
  <h2>Week: {start_s} to {end_s}<span class="badge">Source: TradingEconomics</span></h2>
  {empty_msg}
  <table>
    <thead>
      <tr>
        <th>Country</th>
        <th>When</th>
        <th>Event</th>
        <th>Forecast</th>
        <th>Previous</th>
        <th>Actual</th>
      </tr>
    </thead>
    <tbody>
      {''.join(rows)}
    </tbody>
  </table>
  <div class="foot">Times shown in UTC. Importance: High only. Countries: United States, Canada.</div>
</body>
</html>
    """
    return html

async def render_te_calendar_image(context, html):
    # Render HTML to an image using Playwright
    page = await context.new_page()
    await page.set_content(html, wait_until="load")
    # Make sure it's tall enough
    total = await page.evaluate("document.body.scrollHeight")
    height = max(800, min(total, 4000))
    await page.set_viewport_size({"width": 1200, "height": height})
    await asyncio.sleep(0.5)
    await page.screenshot(path=TE_CAL_PNG, full_page=True)
    await page.close()

async def capture_pinned_tweet_image(context):
    page = await context.new_page()
    print("[Pinned] Navigating…")
    await page.goto("https://x.com/eWhispers")
    await asyncio.sleep(6)
    tweet = await page.query_selector("article")
    if tweet:
        await tweet.screenshot(path=PINNED_TWEET_PNG)
        print(f"[Pinned][OK] Saved: {PINNED_TWEET_PNG}")
    else:
        print("[Pinned][WARN] Pinned tweet not found; skipping.")
    await page.close()

async def main():
    te_api_key = os.environ.get("TE_API_KEY")  # set in GitHub secrets
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            viewport={'width': 1200, 'height': 1200},
            user_agent=("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                        "AppleWebKit/537.36 (KHTML, like Gecko) "
                        "Chrome/120.0.0.0 Safari/537.36")
        )

        # 1) Earnings via pinned tweet
        await capture_pinned_tweet_image(context)

        # 2) Economic calendar via TradingEconomics API
        try:
            if not te_api_key:
                raise RuntimeError("Missing TE_API_KEY")
            events, d1, d2 = fetch_te_events_for_week(te_api_key)
            html = html_for_events(events, d1, d2)
            await render_te_calendar_image(context, html)
            print(f"[TE][OK] Saved: {TE_CAL_PNG}")
        except Exception as e:
            print(f"[TE][ERROR] {e}")
            # Ensure a placeholder is still generated to avoid breaking Slack
            with open(os.path.join(OUTPUT_DIR, "te_error.txt"), "w") as f:
                f.write(str(e))

        await browser.close()

if __name__ == "__main__":
    asyncio.run(main())
