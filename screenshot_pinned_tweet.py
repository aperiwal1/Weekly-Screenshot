import asyncio
import os
import requests
from playwright.async_api import async_playwright
from datetime import datetime

async def screenshot_pinned_tweet():
    date_str = datetime.now().strftime('%Y-%m-%d')
    filepath = f"pinned_tweet_{date_str}.png"

    url = "https://x.com/eWhispers"

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            viewport={'width': 1280, 'height': 1024},
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            )
        )
        page = await context.new_page()

        print("Navigating to X page...")
        await page.goto(url)
        await asyncio.sleep(6)  # Let the page load

        print("Locating pinned tweet...")
        tweet = await page.query_selector('article')  # First visible post
        if tweet:
            await tweet.screenshot(path=filepath)
            print(f"Screenshot saved: {filepath}")
        else:
            print("Pinned tweet not found.")
            return

        await browser.close()

    # === Upload to Slack ===
    webhook_url = os.environ.get("SLACK_WEBHOOK")
    if webhook_url:
        response = requests.post(
            webhook_url,
            json={"text": f"Weekly pinned tweet screenshot captured: {filepath}"}
        )
        if response.status_code == 200:
            print("✅ Message posted to Slack successfully.")
        else:
            print(f"❌ Failed to post to Slack: {response.status_code} {response.text}")
    else:
        print("⚠️ No Slack webhook found in environment variables.")

if __name__ == "__main__":
    asyncio.run(screenshot_pinned_tweet())

