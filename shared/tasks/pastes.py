import os

import requests

from shared.celery_app import celery_app

PASTEBIN_API_KEY = os.getenv("PASTEBIN_API_KEY")


@celery_app.task
def scrape_pastebin_recent():
    """
    Fetch the latest pastes from Pastebin and analyse them.
    Richiede Pastebin Scraping API access.
    """
    if not PASTEBIN_API_KEY:
        return "PASTEBIN_API_KEY is not configured"

    scrape_url = "https://scrape.pastebin.com/api_scraping.php?limit=100"

    try:
        response = requests.get(scrape_url, timeout=30)
        response.raise_for_status()
        pastes = response.json()

        for paste in pastes:
            # Schedule the download and analysis of each individual paste
            analyze_paste_content.delay(paste.get("scrape_url"), paste.get("full_url"))

        return f"Scansionati {len(pastes)} nuovi paste"
    except Exception as e:
        return f"Pastebin error: {e}"


@celery_app.task
def analyze_paste_content(scrape_url, full_url):
    """
    Download a paste's content and match it against every tenant's keywords.
    """
    try:
        response = requests.get(scrape_url, timeout=30)
        response.raise_for_status()
        _ = response.text

        # Keyword matching against tenant keywords goes here
        # e l'applicazione di regole YARA
        # print(f"Analizzando contenuto di {full_url}")

    except Exception as e:
        print(f"Failed to download paste {scrape_url}: {e}")
