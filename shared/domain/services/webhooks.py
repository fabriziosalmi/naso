import hashlib
import hmac
import json
import logging
import os
import time

import httpx
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from ...models import Webhook

logger = logging.getLogger("naso-webhooks")

# Chiave di firma HMAC globale — configura via env per ambienti di produzione.
# Permette ai ricevitori di verificare che l'alert provenga effettivamente da NASO.
_SIGNING_SECRET = os.getenv("NASO_WEBHOOK_SIGNING_SECRET", "").encode()


def _compute_signature(payload_bytes: bytes, timestamp: str) -> str:
    """Compute HMAC-SHA256 over the payload, signing the timestamp too to prevent replay attacks."""
    if not _SIGNING_SECRET:
        return ""
    message = f"{timestamp}.{payload_bytes.decode('utf-8', errors='replace')}".encode()
    return "sha256=" + hmac.new(_SIGNING_SECRET, message, hashlib.sha256).hexdigest()


class WebhookService:
    """
    Gestisce l'invio di notifiche real-time verso Slack/Discord/Teams (U).
    Ogni richiesta include un header HMAC-SHA256 per verifica di integrità (G-12).
    """

    @classmethod
    async def trigger_critical_leak(cls, db: AsyncSession, tenant_id: str, leak_data: dict):
        # 1. Fetch the tenant's active webhooks
        result = await db.execute(select(Webhook).where(Webhook.tenant_id == tenant_id, Webhook.is_active))
        webhooks = result.scalars().all()

        if not webhooks:
            return

        async with httpx.AsyncClient(timeout=10.0) as client:
            for wh in webhooks:
                payload = cls._format_payload(wh.platform, leak_data)
                payload_bytes = json.dumps(payload, ensure_ascii=False).encode()
                timestamp = str(int(time.time()))
                signature = _compute_signature(payload_bytes, timestamp)

                headers = {
                    "Content-Type": "application/json",
                    "X-Naso-Timestamp": timestamp,
                }
                if signature:
                    headers["X-Naso-Signature-256"] = signature

                try:
                    await client.post(wh.url, content=payload_bytes, headers=headers)
                    logger.info(f"[WEBHOOK] Alert sent to {wh.platform} for tenant {tenant_id}")
                except Exception as e:
                    logger.error(f"[WEBHOOK] Failed to send to {wh.platform}: {e}")

    @staticmethod
    def _format_payload(platform: str, data: dict):
        """Format the payload for the target platform."""
        message = (
            f"🚨 [NASO CRITICAL ALERT] 🚨\nSource: {data['source']}\nSeverity: {data['severity']}/100\nID: {data['id']}"
        )

        if platform == "slack":
            return {"text": message}
        elif platform == "discord":
            return {"content": message}

        return {"event": "leak_detected", "data": data}
