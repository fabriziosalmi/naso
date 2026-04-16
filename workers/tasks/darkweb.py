import random
import asyncio
import os
import json
import logging
from ..celery_app import celery_app
from ..utils.stealth_browser import NasoStealthBrowser
from .pipeline import process_potential_leak

logger = logging.getLogger("naso-darkweb")

# Configurazione Proxy Tor (Load Balanced via HAProxy)
TOR_PROXY = os.getenv("TOR_PROXY", "socks5h://naso-tor-lb:8118")
stealth_browser = NasoStealthBrowser(proxy=TOR_PROXY)

@celery_app.task(bind=True, max_retries=5, name="tasks.darkweb.crawl_onion_stealth")
def crawl_onion_stealth(self, onion_url, tenant_id):
    """
    Scansiona una sorgente .onion usando il motore stealth di Naso (#22).
    Invia il risultato alla pipeline di analisi principale.
    """
    try:
        # Percorso temporaneo per lo screenshot (W)
        import time
        screenshot_filename = f"leak_{tenant_id}_{int(time.time())}.png"
        screenshot_path = f"/tmp/{screenshot_filename}"
        
        content = asyncio.run(stealth_browser.get_content_with_screenshot(onion_url, screenshot_path))
        
        if content:
            logger.info(json.dumps({
                "event": "darkweb_crawl_success",
                "url": onion_url,
                "tenant_id": tenant_id,
                "screenshot": screenshot_filename
            }))
            
            # Prepariamo i dati per la pipeline
            hit_data = {
                "tenant_id": tenant_id,
                "source": f"DarkWeb: {onion_url}",
                "screenshot_tmp": screenshot_path,
                "metadata_json": {
                    "url": onion_url,
                    "engine": "NasoStealthBrowser",
                    "timestamp": os.getenv("DATE", "2026-04-15")
                }
            }
            
            # Invio asincrono alla pipeline di analisi
            process_potential_leak.delay(hit_data, content)
            
            return f"Crawl successful for {onion_url}"
        else:
            raise Exception("Empty content or browser failure")
            
    except Exception as e:
        retry_delay = random.randint(300, 900) # Retry più frequente in dev
        logger.warning(json.dumps({
            "event": "darkweb_crawl_retry",
            "url": onion_url,
            "error": str(e),
            "next_retry_seconds": retry_delay
        }))
        raise self.retry(exc=e, countdown=retry_delay)
