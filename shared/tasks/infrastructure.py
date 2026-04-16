from shared.celery_app import celery_app
from shared.tasks.pipeline import process_potential_leak
import logging
import asyncio
import os
import json
import socket
import tempfile
from datetime import datetime

logger = logging.getLogger("naso-infrastructure")

@celery_app.task(bind=True, max_retries=3, queue="osint", name="tasks.infrastructure.scan_exposed_surface")
def scan_exposed_surface(self, target_ip_or_domain: str, tenant_id: str):
    """
    Scansione attiva/passiva della superficie d'attacco.
    In un contesto reale userebbe l'API di Shodan/Censys.
    """
    try:
        logger.info(f"[INFRA RECON] Starting reconnaissance on: {target_ip_or_domain}")
        
        # Simulazione risoluzione target
        try:
            ip_address = socket.gethostbyname(target_ip_or_domain)
        except Exception:
            ip_address = "Unknown"
            
        # Simulazione hit infrastrutturale (Vulnerabilità TLS o porta esposta)
        mock_vuln_report = f"""
        INFRASTRUCTURE OSINT REPORT
        Target: {target_ip_or_domain}
        Resolved IP: {ip_address}
        Date: {datetime.now().isoformat()}
        
        [!] CRITICAL HIT DETECTED
        Port 9200 (Elasticsearch) exposed without authentication.
        CVE-2015-1427 potential vulnerability.
        
        Service Banner:
        "name" : "node-1",
        "cluster_name" : "elasticsearch",
        "version" : {{"number" : "8.12.0"}}
        """
        
        # Preparamos per inviare il rapporto alla pipeline generale NASO
        hit_data = {
            "tenant_id": tenant_id,
            "source": f"Surface Recon: {target_ip_or_domain}",
            "metadata_json": {
                "ip": ip_address,
                "engine": "Naso-Infra-Scanner",
                "target": target_ip_or_domain
            }
        }
        
        # Invia alla main pipeline
        process_potential_leak.delay(hit_data, mock_vuln_report)
        return f"Scan complete for {target_ip_or_domain}"
        
    except Exception as e:
        logger.error(f"[INFRA RECON FAILED] {target_ip_or_domain}: {e}")
        raise self.retry(exc=e, countdown=120)
