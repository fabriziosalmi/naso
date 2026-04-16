import httpx
import logging
import json
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from ...models import Webhook

logger = logging.getLogger("naso-webhooks")

class WebhookService:
    """
    Gestisce l'invio di notifiche real-time verso Slack/Discord/Teams (U).
    """
    
    @classmethod
    async def trigger_critical_leak(cls, db: AsyncSession, tenant_id: str, leak_data: dict):
        # 1. Recupera webhook attivi per il tenant
        result = await db.execute(
            select(Webhook).where(Webhook.tenant_id == tenant_id, Webhook.is_active == True)
        )
        webhooks = result.scalars().all()
        
        if not webhooks:
            return

        async with httpx.AsyncClient(timeout=10.0) as client:
            for wh in webhooks:
                payload = cls._format_payload(wh.platform, leak_data)
                try:
                    await client.post(wh.url, json=payload)
                    logger.info(f"[WEBHOOK] Alert sent to {wh.platform} for tenant {tenant_id}")
                except Exception as e:
                    logger.error(f"[WEBHOOK] Failed to send to {wh.url}: {e}")

    @staticmethod
    def _format_payload(platform: str, data: dict):
        """Formatta il payload in base alla piattaforma."""
        message = f"🚨 [NASO CRITICAL ALERT] 🚨\nSource: {data['source']}\nSeverity: {data['severity']}/100\nID: {data['id']}"
        
        if platform == "slack":
            return {"text": message}
        elif platform == "discord":
            return {"content": message}
        
        return {"event": "leak_detected", "data": data}
