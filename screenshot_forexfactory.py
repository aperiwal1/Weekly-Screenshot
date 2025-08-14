import asyncio
from playwright.async_api import async_playwright
from datetime import datetime
import os

# Output path
OUTPUT_DIR = "screenshots"
os.makedirs(OUTPUT_DIR, exist_ok=True)

async def screenshot_pinned_tweet():
    date_str = datetime.now().strftime('%Y-%m-%d')
    filepath = os.path.join(OUTPUT_DIR, f"eWhispers_pinned_{date_str}.png")

    url = "https://x.com/eWhispers"

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
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
        await asyncio.sleep(6)  # Wait instead of networkidle

        # Accept cookies if needed
        try:
            await page.click('text=Accept all cookies')
            print("Cookies accepted.")
            await asyncio.sleep(1)
        except:
            print("No cookie popup.")

        # Locate first tweet (pinned)
        print("Locating pinned tweet...")
        try:
            tweet = await page.query_selector('article')  # First visible post
            if tweet:
                await tweet.screenshot(path=filepath)
                print(f"Pinned tweet screenshot saved to {filepath}")
            else:
                print("Pinned tweet not found.")
        except Exception as e:
            print(f"Error capturing tweet: {e}")

        await browser.close()

if __name__ == "__main__":
    asyncio.run(screenshot_pinned_tweet())
