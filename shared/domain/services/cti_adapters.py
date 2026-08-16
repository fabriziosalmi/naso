import logging

import aiohttp

logger = logging.getLogger("naso-cti")


class CTIAdapters:
    """
    NASO CTI Enchancer API
    Modulo "Keyless" per OSINT passivo. Scrape and open APIs.
    """

    @classmethod
    async def fetch_btc_balance(cls, btc_address: str) -> dict:
        """
        [Blockchain OSINT] Fetch the balance from blockchain.info, no API key required.
        Utile per valutare il volume economico di un Ransomware gang target.
        """
        logger.info(f"[CTI ADAPTER] Fetching Blockchain data for {btc_address}")
        url = f"https://blockchain.info/rawaddr/{btc_address}"

        async with aiohttp.ClientSession() as session:
            try:
                # rate limit friendly timeout
                async with session.get(url, timeout=10) as response:
                    if response.status == 200:
                        data = await response.json()
                        balance_satoshi = data.get("final_balance", 0)
                        total_received = data.get("total_received", 0)

                        return {
                            "btc_address": btc_address,
                            "balance_btc": balance_satoshi / 100000000.0,
                            "total_received_btc": total_received / 100000000.0,
                            "tx_count": data.get("n_tx", 0),
                        }
                    else:
                        logger.warning(f"[CTI BTC] Blockchain API returned {response.status}")
                        return {}
            except Exception as e:
                logger.error(f"[CTI BTC] Request failed: {e}")
                return {}

    @classmethod
    async def fetch_threatfox_ioc(cls, search_term: str) -> dict:
        """
        [AlienVault / ThreatFox fallback] Open POST keyless.
        Useful for quickly correlating IPs or domains extracted by the Babel node.
        """
        logger.info(f"[CTI ADAPTER] Querying ThreatFox for {search_term}")
        url = "https://threatfox-api.abuse.ch/api/v1/"
        payload = {"query": "search_ioc", "search_term": search_term}

        async with aiohttp.ClientSession() as session:
            try:
                async with session.post(url, json=payload, timeout=10) as response:
                    if response.status == 200:
                        data = await response.json()
                        if data.get("query_status") == "ok":
                            return {"threatfox_matches": data.get("data", [])[:3]}  # Return top 3
                        return {}
                    else:
                        return {}
            except Exception as e:
                logger.error(f"[CTI THREATFOX] Request failed: {e}")
                return {}
