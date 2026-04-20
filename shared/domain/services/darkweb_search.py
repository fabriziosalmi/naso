import logging

import httpx
from bs4 import BeautifulSoup

logger = logging.getLogger("naso-darkweb-search")


class DarkWebSearchService:
    """
    Integrazione con motori di ricerca Dark Web (es. Ahmia) per leak storici (AA).
    """

    AHMIA_URL = "https://ahmia.fi/search/"

    @classmethod
    async def search_onion_links(cls, query: str) -> list[dict]:
        """
        Esegue una ricerca su Ahmia per individuare link .onion correlati alle keyword.
        Parsa la risposta HTML reale — nessun dato mock.
        """
        params = {"q": query}
        results = []

        try:
            async with httpx.AsyncClient(
                timeout=20.0,
                headers={"User-Agent": "Mozilla/5.0 (compatible; NASO-Forensic/1.1)"},
                follow_redirects=True,
            ) as client:
                response = await client.get(cls.AHMIA_URL, params=params)
                response.raise_for_status()

            soup = BeautifulSoup(response.text, "html.parser")

            for item in soup.select("li.result"):
                title_el = item.select_one("h4")
                url_el = item.select_one("p.onion-site, cite")
                desc_el = item.select_one("p.description")

                title = title_el.get_text(strip=True) if title_el else "(no title)"
                url = url_el.get_text(strip=True) if url_el else ""
                desc = desc_el.get_text(strip=True) if desc_el else ""

                if url:
                    results.append({"title": title, "url": url, "description": desc})

            logger.info(f"[DARK SEARCH] Query '{query}' returned {len(results)} results from Ahmia.")
            return results

        except httpx.HTTPStatusError as e:
            logger.error(f"[DARK SEARCH] Ahmia HTTP error {e.response.status_code} for query '{query}'")
            raise ValueError(f"Dark Web search failed: HTTP {e.response.status_code}")
        except Exception as e:
            logger.error(f"[DARK SEARCH] Error during Ahmia search: {e}")
            raise ValueError(f"Dark Web node unreachable: {str(e)}")
