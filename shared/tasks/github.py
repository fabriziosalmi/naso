import logging
import os
from urllib.parse import quote

import httpx

from shared.celery_app import celery_app

GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")
logger = logging.getLogger("naso-github")

# P-10: module-level persistent client — reuses TCP connection + TLS session across task invocations.
# Creating httpx.Client() inside the task pays ~150ms TLS handshake overhead every call.
_github_client: httpx.Client | None = None


def _get_github_client() -> httpx.Client:
    global _github_client
    if _github_client is None:
        _github_client = httpx.Client(
            timeout=30,
            headers={
                "Authorization": f"token {GITHUB_TOKEN}",
                "Accept": "application/vnd.github.v3+json",
            },
            limits=httpx.Limits(max_keepalive_connections=5, max_connections=10),
        )
    return _github_client


@celery_app.task(bind=True, max_retries=3)
def scan_github_for_keyword(self, keyword_value, tenant_id):
    """
    Scan GitHub for a specific keyword belonging to a tenant.
    Uses httpx (non-blocking) instead of requests (synchronous, blocking) — G-08.
    """
    if not GITHUB_TOKEN:
        logger.error("GITHUB_TOKEN is not configured.")
        return

    # quote() sanitises the keyword to prevent URL/parameter injection (G-09)
    safe_keyword = quote(str(keyword_value), safe="")
    search_url = f"https://api.github.com/search/code?q={safe_keyword}"

    try:
        client = _get_github_client()  # P-10: reuse persistent connection pool
        response = client.get(search_url)

        if response.status_code == 403:  # Rate limit
            retry_after = int(response.headers.get("Retry-After", 60))
            raise self.retry(countdown=retry_after)

        response.raise_for_status()
        results = response.json()

        hits = []
        for item in results.get("items", []):
            hit_data = {
                "tenant_id": tenant_id,
                "source": "github",
                "content_snippet": item.get("path"),
                "raw_data_url": item.get("html_url"),
                "metadata_json": {"repository": item.get("repository", {}).get("full_name"), "sha": item.get("sha")},
                "severity_score": 5,  # Baseline score, refined later by YARA
            }
            hits.append(hit_data)
            logger.info(f"Trovato potenziale leak su GitHub: {item.get('html_url')}")

        return len(hits)

    except Exception as e:
        logger.error(f"GitHub scan failed for {keyword_value}: {e}")
        raise self.retry(exc=e, countdown=300)
