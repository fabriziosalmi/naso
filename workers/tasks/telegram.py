import os
import asyncio
import logging
from ..celery_app import celery_app
from .pipeline import process_potential_leak
from telethon import TelegramClient

logger = logging.getLogger("naso-telegram")

# Configurazione Telegram (#23)
API_ID = os.getenv("TELEGRAM_API_ID")
API_HASH = os.getenv("TELEGRAM_API_HASH")
SESSION_NAME = os.getenv("TELEGRAM_SESSION_NAME", "naso_forensic")

@celery_app.task(bind=True, name="tasks.telegram.monitor_channel")
def monitor_telegram_channel(self, channel_username, tenant_id):
    """
    Innesca il monitoraggio di un canale Telegram specifico.
    In un sistema di produzione, questo potrebbe far partire un processo a lunga durata
    o fare uno scraping periodico degli ultimi messaggi.
    """
    if not API_ID or not API_HASH:
        logger.warning("[TELEGRAM] API_ID or API_HASH not set. Telegram Intelligence is in DRY-RUN mode.")
        return "Telegram API keys missing, skipping monitor."

    asyncio.run(scrape_telegram_channel(channel_username, tenant_id))
    return f"Monitoring initiated for {channel_username}"

async def scrape_telegram_channel(channel_username, tenant_id):
    """
    Scrape degli ultimi messaggi da un canale Telegram.
    """
    async with TelegramClient(SESSION_NAME, API_ID, API_HASH) as client:
        logger.info(f"[TELEGRAM] Scraping channel: {channel_username} for tenant {tenant_id}")
        
        try:
            async for message in client.iter_messages(channel_username, limit=50):
                if message.text:
                    # Prepariamo i dati per la pipeline
                    hit_data = {
                        "tenant_id": tenant_id,
                        "source": f"Telegram: {channel_username}",
                        "metadata_json": {
                            "message_id": message.id,
                            "date": message.date.isoformat() if message.date else None,
                            "channel": channel_username
                        }
                    }
                    
                    # Invio asincrono alla pipeline di analisi Naso
                    process_potential_leak.delay(hit_data, message.text)
                    
            logger.info(f"[TELEGRAM] Scraping complete for {channel_username}")
        except Exception as e:
            logger.error(f"[TELEGRAM] Failed to scrape {channel_username}: {e}")

@celery_app.task(name="tasks.telegram.process_message")
def process_telegram_message(message_text, channel_name, tenant_id):
    """
    Processa un singolo messaggio Telegram (usato ad esempio per i webhook/bot).
    """
    hit_data = {
        "tenant_id": tenant_id,
        "source": f"Telegram: {channel_name}",
        "metadata_json": {"channel": channel_name}
    }
    process_potential_leak.delay(hit_data, message_text)
    return "Telegram message sent to pipeline"
