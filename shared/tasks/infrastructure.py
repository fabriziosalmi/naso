import logging
import os
import socket
from datetime import datetime, timezone

import httpx

from shared.celery_app import celery_app
from shared.config import settings
from shared.tasks.pipeline import process_potential_leak

logger = logging.getLogger("naso-infrastructure")


def _resolve_target(target: str) -> str:
    """Risolve hostname → IP. Ritorna 'Unknown' se la risoluzione fallisce."""
    try:
        return socket.gethostbyname(target)
    except Exception:
        return "Unknown"


def _probe_common_ports(ip: str, ports: list[int] = None) -> list[dict]:
    """Proba le porte in PARALLELO con ThreadPoolExecutor (P-07).
    Tempo totale: max(timeout singolo) invece di N×timeout sequenziale.
    Worst case passa da 26s (13 porte × 2s) a 1s.
    """
    if ports is None:
        ports = [21, 22, 23, 25, 80, 443, 3306, 5432, 6379, 8080, 8443, 9200, 27017]

    def _probe(port: int):
        try:
            with socket.create_connection((ip, port), timeout=1):
                return {"port": port, "state": "open"}
        except (socket.timeout, ConnectionRefusedError, OSError):
            return None

    from concurrent.futures import ThreadPoolExecutor
    with ThreadPoolExecutor(max_workers=len(ports)) as ex:
        return [r for r in ex.map(_probe, ports) if r is not None]


@celery_app.task(bind=True, max_retries=3, queue="osint", name="tasks.infrastructure.scan_exposed_surface")
def scan_exposed_surface(self, target_ip_or_domain: str, tenant_id: str):
    """
    Scansione passiva della superficie d'attacco tramite risoluzione DNS e
    probe TCP sulle porte comuni. Se SHODAN_API_KEY è configurata, arricchisce
    il risultato con i dati Shodan.
    """
    try:
        logger.info(f"[INFRA RECON] Starting reconnaissance on: {target_ip_or_domain}")

        ip_address = _resolve_target(target_ip_or_domain)
        open_ports = _probe_common_ports(ip_address) if ip_address != "Unknown" else []

        report_lines = [
            "INFRASTRUCTURE OSINT REPORT",
            f"Target: {target_ip_or_domain}",
            f"Resolved IP: {ip_address}",
            f"Date: {datetime.now(timezone.utc).isoformat()}",
            "",
            f"Open ports detected: {[p['port'] for p in open_ports] or 'none'}",
        ]

        # Arricchimento Shodan opzionale
        if settings.SHODAN_API_KEY and ip_address != "Unknown":
            try:
                resp = httpx.get(
                    f"https://api.shodan.io/shodan/host/{ip_address}",
                    params={"key": settings.SHODAN_API_KEY},
                    timeout=10.0,
                )
                if resp.status_code == 200:
                    data = resp.json()
                    vulns = data.get("vulns", [])
                    if vulns:
                        report_lines.append(f"Shodan CVEs: {', '.join(vulns)}")
                    report_lines.append(f"Shodan org: {data.get('org', 'N/A')}")
            except Exception as shodan_err:
                logger.warning(f"[INFRA RECON] Shodan enrichment failed: {shodan_err}")

        report = "\n".join(report_lines)

        if not open_ports:
            logger.info(f"[INFRA RECON] No open ports found on {target_ip_or_domain} — no hit queued.")
            return f"Scan complete for {target_ip_or_domain}: no open ports detected."

        hit_data = {
            "tenant_id": tenant_id,
            "source": f"Surface Recon: {target_ip_or_domain}",
            "metadata_json": {
                "ip": ip_address,
                "engine": "Naso-Infra-Scanner",
                "target": target_ip_or_domain,
                "open_ports": open_ports,
            },
        }

        process_potential_leak.delay(hit_data, report)
        return f"Scan complete for {target_ip_or_domain}: {len(open_ports)} open port(s) queued for analysis."

    except Exception as e:
        logger.error(f"[INFRA RECON FAILED] {target_ip_or_domain}: {e}")
        raise self.retry(exc=e, countdown=120)
