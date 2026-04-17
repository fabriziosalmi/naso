import httpx
import logging
import re
from typing import List, Dict, Any

logger = logging.getLogger(__name__)

class TelegramOSINTService:
    """
    Zero-Auth Telegram OSINT Scraper.
    Fetches the public web preview (t.me/s/) of Telegram channels and extracts
    the most recent messages. Ideal for monitoring Ransomware leak channels, 
    hacktivist groups, or infosec news without requiring MTProto auth/SMS.
    """
    
    @classmethod
    async def scrape_public_channel(cls, channel_name: str, limit: int = 15) -> List[Dict[str, Any]]:
        """
        Scrapes a public Telegram channel directly via HTTP.
        """
        # Clean channel name (remove @ or t.me/ prefixes)
        channel_name = channel_name.replace("@", "").replace("t.me/", "").replace("https://", "").strip()
        
        # We use the web preview /s/ URL
        url = f"https://t.me/s/{channel_name}"
        
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.5",
        }
        
        async with httpx.AsyncClient(timeout=15.0, follow_redirects=True) as client:
            try:
                response = await client.get(url, headers=headers)
                
                if response.status_code == 404:
                    return [{"error": f"Channel '{channel_name}' not found or is strictly private."}]
                
                response.raise_for_status()
                html = response.text
                
                # Check if it's actually a channel preview
                if "tgme_widget_message_wrap" not in html:
                    return [{"error": "Channel preview not available. It might be private or blocked."}]
                
                # Basic HTML regex parsing (avoids BeautifulSoup dependency overhead for simple widget extraction)
                # This regex captures the message text blocks
                msg_pattern = re.compile(r'<div class="tgme_widget_message_text[^>]*>(.*?)</div>', re.DOTALL)
                date_pattern = re.compile(r'<time datetime="([^"]+)"', re.DOTALL)
                views_pattern = re.compile(r'<span class="tgme_widget_message_views">([^<]+)</span>', re.DOTALL)
                
                # We split by message wrap to keep pieces correlated
                wraps = html.split('<div class="tgme_widget_message_wrap')
                
                results = []
                for wrap in wraps[1:]:  # skip the first split which is the header
                    text_match = msg_pattern.search(wrap)
                    if not text_match:
                        continue
                        
                    # Clean HTML tags and decode entities manually
                    raw_text = text_match.group(1)
                    clean_text = re.sub(r'<br\s*/?>', '\n', raw_text)
                    clean_text = re.sub(r'<[^>]+>', '', clean_text)
                    clean_text = clean_text.replace('&quot;', '"').replace('&amp;', '&').replace('&#39;', "'").replace('&lt;', '<').replace('&gt;', '>')
                    
                    date_match = date_pattern.search(wrap)
                    timestamp = date_match.group(1) if date_match else "unknown"
                    
                    views_match = views_pattern.search(wrap)
                    views = views_match.group(1) if views_match else "unknown"
                    
                    results.append({
                        "channel": channel_name,
                        "timestamp": timestamp,
                        "views": views,
                        "text": clean_text.strip()
                    })
                
                # Sort from newest (assume last in HTML is newest) and reverse it, then limit
                results = results[::-1][:limit]
                return results

            except httpx.HTTPError as e:
                logger.error(f"Telegram scrape error for {channel_name}: {e}")
                return [{"error": f"HTTP Error during scrape: {str(e)}"}]
            except Exception as e:
                logger.exception("Unexpected error in Telegram scraper")
                return [{"error": f"Scraper Exception: {str(e)}"}]
