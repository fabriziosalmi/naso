import asyncio
import json
import logging
import os
import secrets
import tempfile

from shared.celery_app import celery_app
from shared.utils.stealth_browser import NasoStealthBrowser

from .pipeline import process_potential_leak

logger = logging.getLogger("naso-darkweb")

# Tor proxy configuration (load balanced via HAProxy)
TOR_PROXY = os.getenv("TOR_PROXY", "socks5h://naso-tor-lb:8118")
stealth_browser = NasoStealthBrowser(proxy=TOR_PROXY)

from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup


@celery_app.task(bind=True, max_retries=3, name="tasks.darkweb.deep_portal_crawl")
def deep_portal_crawl(self, root_url, tenant_id, max_pages=10):
    """
    Recursive crawler for onion portals (#22).
    Walks the site from its root and pushes every relevant page into the pipeline.
    """
    try:
        visited = set()
        to_visit = [root_url]
        pages_crawled = 0

        # P-06: allocate the event loop ONCE for the entire crawl job.
        # Creating and tearing down a new loop per page wastes selector init overhead N times.
        import time

        loop = asyncio.new_event_loop()
        try:
            while to_visit and pages_crawled < max_pages:
                url = to_visit.pop(0)
                if url in visited:
                    continue

                screenshot_filename = f"deep_leak_{tenant_id}_{int(time.time())}.png"
                screenshot_path = os.path.join(tempfile.gettempdir(), screenshot_filename)

                content = loop.run_until_complete(stealth_browser.get_content_with_screenshot(url, screenshot_path))
                visited.add(url)

                # This block belongs INSIDE the while loop. It was indented
                # one level out, so the crawl popped a page, screenshotted it,
                # marked it visited — and never processed it, never counted it,
                # and never queued its links. The loop therefore drained the
                # initial [root_url] in one pass and stopped: a "deep recursive
                # crawl" that scanned exactly one page and reported
                # pages_crawled from a counter it never incremented (and would
                # raise NameError on `content` if max_pages were 0).
                if content:
                    # Cap the content size to keep the worker from running out of memory (G-07)
                    # A malicious onion page over 1MB would be truncated before it is
                    # handed to the AI pipeline and indexed.
                    MAX_CONTENT_BYTES = 1 * 1024 * 1024  # 1 MB
                    if len(content) > MAX_CONTENT_BYTES:
                        logger.warning(
                            f"[DEEP CRAWL] Content truncated for {url} ({len(content)} bytes > {MAX_CONTENT_BYTES})"
                        )
                        content = content[:MAX_CONTENT_BYTES]

                    pages_crawled += 1
                    logger.info(f"[DEEP CRAWL] Scanned {url} ({pages_crawled}/{max_pages})")

                    # Push into the pipeline
                    hit_data = {
                        "tenant_id": tenant_id,
                        "source": f"DarkWeb Deep: {root_url}",
                        "screenshot_tmp": screenshot_path,
                        "metadata_json": {"url": url, "depth": "recursive"},
                    }
                    process_potential_leak.delay(hit_data, content)

                    # Extract internal links
                    soup = BeautifulSoup(content, "html.parser")
                    for link in soup.find_all("a", href=True):
                        href = link["href"]
                        full_url = urljoin(url, href)

                        # Stay within the same .onion domain
                        if urlparse(full_url).netloc == urlparse(root_url).netloc:
                            if full_url not in visited and full_url not in to_visit:
                                to_visit.append(full_url)
        finally:
            loop.close()

        return f"Deep crawl complete for {root_url}. Scanned {pages_crawled} pages."

    except Exception as e:
        logger.error(f"[DEEP CRAWL FAILED] {root_url}: {e}")
        raise self.retry(exc=e, countdown=600)


@celery_app.task(bind=True, max_retries=5, name="tasks.darkweb.crawl_onion_stealth")
def crawl_onion_stealth(self, onion_url, tenant_id):
    """
    Scan an .onion source using the NASO stealth engine (#22).
    Forwards the result to the main analysis pipeline.
    """
    try:
        # Temporary path for the screenshot (W)
        import time

        screenshot_filename = f"leak_{tenant_id}_{int(time.time())}.png"
        screenshot_path = os.path.join(tempfile.gettempdir(), screenshot_filename)

        loop = asyncio.new_event_loop()
        try:
            content = loop.run_until_complete(stealth_browser.get_content_with_screenshot(onion_url, screenshot_path))
        finally:
            loop.close()

        if content:
            logger.info(
                json.dumps(
                    {
                        "event": "darkweb_crawl_success",
                        "url": onion_url,
                        "tenant_id": tenant_id,
                        "screenshot": screenshot_filename,
                    }
                )
            )

            # Prepare the payload for the pipeline
            hit_data = {
                "tenant_id": tenant_id,
                "source": f"DarkWeb: {onion_url}",
                "screenshot_tmp": screenshot_path,
                "metadata_json": {
                    "url": onion_url,
                    "engine": "NasoStealthBrowser",
                    "timestamp": os.getenv("DATE", "2026-04-15"),
                },
            }

            # Asynchronous dispatch into the analysis pipeline
            process_potential_leak.delay(hit_data, content)

            return f"Crawl successful for {onion_url}"
        else:
            raise Exception("Empty content or browser failure")

    except Exception as e:
        retry_delay = 300 + secrets.randbelow(601)  # More frequent retries in development
        logger.warning(
            json.dumps(
                {"event": "darkweb_crawl_retry", "url": onion_url, "error": str(e), "next_retry_seconds": retry_delay}
            )
        )
        raise self.retry(exc=e, countdown=retry_delay)
