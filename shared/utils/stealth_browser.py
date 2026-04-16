import asyncio
from playwright.async_api import async_playwright
from playwright_stealth import stealth_async
import secrets

class NasoStealthBrowser:
    def __init__(self, proxy=None):
        self.proxy = proxy

    async def get_content_with_screenshot(self, url, screenshot_path=None):
        """
        Navigazione stealth con cattura screenshot per prove visuali (W).
        """
        async with async_playwright() as p:
            browser = await p.chromium.launch(
                headless=True,
                proxy={"server": self.proxy} if self.proxy else None,
                args=["--no-sandbox", "--disable-setuid-sandbox"]
            )
            context = await browser.new_context(
                viewport={'width': 1280, 'height': 720},
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/116.0.0.0 Safari/537.36"
            )
            page = await context.new_page()
            await stealth_async(page)
            
            try:
                await page.goto(url, wait_until="networkidle", timeout=60000)
                await asyncio.sleep(2 + secrets.SystemRandom().random() * 2) # Attesa rendering dinamico
                
                content = await page.content()
                
                if screenshot_path:
                    await page.screenshot(path=screenshot_path, full_page=True)
                    
                return content
            except Exception as e:
                print(f"OPSEC Failure during crawl/screenshot: {e}")
                return None
            finally:
                await browser.close()

    async def get_content(self, url):
        return await self.get_content_with_screenshot(url)
