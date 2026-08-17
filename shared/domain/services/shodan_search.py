import ipaddress
import logging
from typing import Any

import httpx

from shared.config import settings

logger = logging.getLogger(__name__)


class ShodanService:
    """
    OSINT Service to perform Shodan infrastructure mapping without needing heavy SDK dependencies.
    Relies on SHODAN_API_KEY from config.
    """

    BASE_URL = "https://api.shodan.io"

    @classmethod
    async def scan_host(cls, ip: str) -> dict[str, Any]:
        """
        Query Shodan for information about a specific IP address.
        """
        if not settings.SHODAN_API_KEY:
            logger.error("SHODAN_API_KEY is not configured.")
            raise ValueError("Shodan integration is disabled (missing API key).")

        # Validate here, in the service, not only at the HTTP endpoint. The MCP
        # tool (naso_shodan_scan) reaches this path without going through the
        # endpoint's ipaddress check, so an unvalidated value was interpolated
        # straight into the request path. Rejecting a non-IP closes that and
        # avoids a wasted, malformed upstream call.
        try:
            ipaddress.ip_address(str(ip).strip())
        except ValueError:
            return {"error": f"Not a valid IP address: {ip!r}"}
        ip = str(ip).strip()

        async with httpx.AsyncClient(timeout=15.0) as client:
            try:
                # GET https://api.shodan.io/shodan/host/{ip}?key={key}
                url = f"{cls.BASE_URL}/shodan/host/{ip}"
                response = await client.get(url, params={"key": settings.SHODAN_API_KEY})

                if response.status_code == 404:
                    return {"error": "No information found for this IP."}

                response.raise_for_status()
                data = response.json()

                # Extract clean, LLM-friendly subset of data to avoid context overflow
                return {
                    "ip_str": data.get("ip_str"),
                    "org": data.get("org"),
                    "isp": data.get("isp"),
                    "os": data.get("os"),
                    "ports": data.get("ports", []),
                    "hostnames": data.get("hostnames", []),
                    "vulns": data.get("vulns", []),  # CVE list if available
                    "data_summary": [
                        {"port": d.get("port"), "product": d.get("product"), "version": d.get("version")}
                        for d in data.get("data", [])
                    ],
                }
            except httpx.HTTPStatusError as e:
                logger.error(f"Shodan API error for IP {ip}: {e.response.text}")
                return {"error": f"API Error: {e.response.status_code}"}
            except Exception as e:
                logger.exception("Shodan network error")
                return {"error": str(e)}

    @classmethod
    async def search_query(cls, query: str) -> dict[str, Any]:
        """
        Search Shodan using a dork query (e.g. 'nginx port:80').
        Requires Developer-tier Shodan API key.
        """
        if not settings.SHODAN_API_KEY:
            raise ValueError("Shodan integration is disabled.")

        async with httpx.AsyncClient(timeout=15.0) as client:
            try:
                url = f"{cls.BASE_URL}/shodan/host/search"
                response = await client.get(url, params={"key": settings.SHODAN_API_KEY, "query": query})
                response.raise_for_status()
                data = response.json()

                matches = data.get("matches", [])
                results = []
                for m in matches[:10]:  # Limit to 10 for AI context
                    results.append(
                        {
                            "ip": m.get("ip_str"),
                            "port": m.get("port"),
                            "org": m.get("org"),
                            "product": m.get("product"),
                            "timestamp": m.get("timestamp"),
                        }
                    )

                return {"total_matches": data.get("total", 0), "results": results}
            except Exception as e:
                return {"error": str(e)}
