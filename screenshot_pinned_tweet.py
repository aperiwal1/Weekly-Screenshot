import asyncio
import os
from playwright.async_api import async_playwright
from datetime import datetime

# Save into "site/" so GitHub Pages can publish it
OUTPUT_DIR = "site"
os.makedirs(OUTPUT_DIR, exist_ok=True)

async def screenshot_pinned_tweet():
    # Stable file name so the URL stays the same week to week
    filepath = os.path.join(OUTPUT_DIR, "pinned_tweet.png")

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
        await asyncio.sleep(6)

        print("Locating pinned tweet...")
        tweet = await page.query_selector('article')
        if not tweet:
            print("[ERROR] Pinned tweet not found.")
            await browser.close()
            return

        await tweet.screenshot(path=filepath)
        print(f"[SUCCESS] Screenshot saved: {filepath}")

        await browser.close()

if __name__ == "__main__":
    asyncio.run(screenshot_pinned_tweet())
