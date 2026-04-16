import requests
from shared.celery_app import celery_app
import os

GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")

@celery_app.task(bind=True, max_retries=3)
def scan_github_for_keyword(self, keyword_value, tenant_id):
    """
    Scansiona GitHub per una specifica keyword legata a un tenant.
    """
    if not GITHUB_TOKEN:
        print("Errore: GITHUB_TOKEN non configurato.")
        return

    headers = {
        "Authorization": f"token {GITHUB_TOKEN}",
        "Accept": "application/vnd.github.v3+json"
    }
    
    # Query di ricerca: cerca la keyword nel codice pubblico
    search_url = f"https://api.github.com/search/code?q={keyword_value}"
    
    try:
        response = requests.get(search_url, headers=headers, timeout=30)
        
        if response.status_code == 403: # Rate limit
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
                "metadata_json": {
                    "repository": item.get("repository", {}).get("full_name"),
                    "sha": item.get("sha")
                },
                "severity_score": 5 # Score base da raffinare con YARA
            }
            hits.append(hit_data)
            # Invia a un'altra task per l'analisi profonda e il salvataggio
            # analyze_leak.delay(hit_data)
            print(f"Trovato potenziale leak su GitHub: {item.get('html_url')}")
            
        return len(hits)
        
    except Exception as e:
        print(f"Errore durante lo scan GitHub per {keyword_value}: {e}")
        raise self.retry(exc=e, countdown=300)
