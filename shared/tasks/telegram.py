import os
import asyncio
import logging
from shared.celery_app import celery_app
from .pipeline import process_potential_leak
from telethon import TelegramClient

logger = logging.getLogger("naso-telegram")

# Configurazione Telegram (#23)
API_ID = os.getenv("TELEGRAM_API_ID")
API_HASH = os.getenv("TELEGRAM_API_HASH")
SESSION_NAME = os.getenv("TELEGRAM_SESSION_NAME", "naso_forensic")

from telethon import TelegramClient, events
import json

@celery_app.task(bind=True, name="tasks.telegram.start_realtime_listener")
def start_realtime_listener(self, tenant_id, channels: list):
    """
    Avvia un listener real-time per una lista di canali Telegram (#23).
    Questo task è a lunga durata e monitora i canali in tempo reale.
    """
    if not API_ID or not API_HASH:
        logger.error("[TELEGRAM] API_ID or API_HASH not set. Cannot start real-time listener.")
        return

    loop = asyncio.get_event_loop()
    loop.run_until_complete(run_telethon_listener(tenant_id, channels))

async def run_telethon_listener(tenant_id, channels):
    """
    Esegue il client Telethon in modalità ascolto eventi.
    """
    async with TelegramClient(SESSION_NAME, API_ID, API_HASH) as client:
        logger.info(f"[TELEGRAM REAL-TIME] Monitoring started for tenant {tenant_id} on channels: {channels}")
        
        # Gestore eventi per nuovi messaggi
        @client.on(events.NewMessage(chats=channels))
        async def handler(event):
            if event.message.text:
                logger.info(f"[TELEGRAM EVENT] New message in {event.chat.title or event.chat_id}")
                hit_data = {
                    "tenant_id": tenant_id,
                    "source": f"Telegram Real-time: {event.chat.title or event.chat_id}",
                    "metadata_json": {
                        "message_id": event.message.id,
                        "date": event.message.date.isoformat() if event.message.date else None,
                        "from_id": str(event.message.from_id) if event.message.from_id else None
                    }
                }
                # Invio alla pipeline
                process_potential_leak.delay(hit_data, event.message.text)

        # Mantiene il client in esecuzione
        await client.run_until_disconnected()

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
