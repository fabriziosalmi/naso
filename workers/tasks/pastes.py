import requests
from ..celery_app import celery_app
import os

PASTEBIN_API_KEY = os.getenv("PASTEBIN_API_KEY")

@celery_app.task
def scrape_pastebin_recent():
    """
    Recupera gli ultimi paste da Pastebin e li analizza.
    Richiede Pastebin Scraping API access.
    """
    if not PASTEBIN_API_KEY:
        return "PASTEBIN_API_KEY non configurato"
        
    scrape_url = "https://scrape.pastebin.com/api_scraping.php?limit=100"
    
    try:
        response = requests.get(scrape_url, timeout=30)
        response.raise_for_status()
        pastes = response.json()
        
        for paste in pastes:
            # Schedula il download e l'analisi del contenuto del singolo paste
            analyze_paste_content.delay(paste.get("scrape_url"), paste.get("full_url"))
            
        return f"Scansionati {len(pastes)} nuovi paste"
    except Exception as e:
        return f"Errore Pastebin: {e}"

@celery_app.task
def analyze_paste_content(scrape_url, full_url):
    """
    Scarica il contenuto di un paste e lo confronta con le keyword di tutti i tenant.
    """
    try:
        response = requests.get(scrape_url, timeout=30)
        response.raise_for_status()
        _ = response.text
        
        # Qui implementeremo la logica di confronto con le keyword dei tenant
        # e l'applicazione di regole YARA
        # print(f"Analizzando contenuto di {full_url}")
        
    except Exception as e:
        print(f"Errore download paste {scrape_url}: {e}")
