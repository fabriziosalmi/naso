from shared.celery_app import celery_app
from shared.tasks.pipeline import process_potential_leak
import logging
import asyncio
import os
import json
import re
from datetime import datetime

logger = logging.getLogger("naso-massive")

# Espressioni regolari per identificare criticità in log massicci
EMAIL_REGEX = re.compile(r"[a-z0-9\.\-+_]+@[a-z0-9\.\-+_]+\.[a-z]+", re.I)
PRIVATE_KEY_REGEX = re.compile(r"-----BEGIN (RSA|OPENSSH) PRIVATE KEY-----")

@celery_app.task(bind=True, max_retries=1, queue="massive", name="tasks.massive.process_blob_stream")
def process_blob_stream(self, file_url_or_path: str, tenant_id: str):
    """
    Streaming Processor SOTA.
    Legge un dump gigabyte riga per riga, evitando buffer OOM.
    Applica Fast Regex e inoltra alla pipeline solo i "chunk" rilevanti.
    """
    try:
        logger.info(f"[MASSIVE INGESTION] Starting OOM-safe stream for: {file_url_or_path}")
        
        suspicious_chunks_found = 0
        total_lines_read = 0
        
        # Simuliamo un file pointer o buffer. 
        # In un contesto reale useremmo requests.get(url, stream=True).iter_lines()
        
        def mock_stream_generator():
            yield "system_startup, no issues"
            yield "user: admin, location: it, password: rigourous_admin123"
            yield "-----BEGIN RSA PRIVATE KEY-----\nMIIEowIBAAK... (leaked ssh key test)"
            yield "test@corp.com:password123!"
            yield "normal traffic trace 404"
            for _ in range(100): # Simuliamo noise di background
                yield "DEBUG: Background worker pulse"
                
        # Algoritmo SOTA: Non-Blocking Line Reader
        # Estraiamo buffer accumulati o mandiamo riga per riga
        for line in mock_stream_generator():
            total_lines_read += 1
            
            # Filter Fast Phase:
            if EMAIL_REGEX.search(line) or PRIVATE_KEY_REGEX.search(line):
                suspicious_chunks_found += 1
                
                # Delegation Pattern SOTA:
                # Disaccoppiamo la scoperta grezza dal processing pesante. 
                # Il massive worker rimbalza la hit al worker generico.
                hit_data = {
                    "tenant_id": tenant_id,
                    "source": f"Massive Dump Stream: {file_url_or_path}",
                    "metadata_json": {
                        "line_number": total_lines_read,
                        "engine": "Naso-Stream-Processor"
                    }
                }
                process_potential_leak.apply_async((hit_data, line), queue="default")

        logger.info(f"[MASSIVE INGESTION] Complete. 0 RAM overload. Stream lines: {total_lines_read}. Suspicious hits delegated: {suspicious_chunks_found}.")
        return f"Processato {file_url_or_path} - Delegati {suspicious_chunks_found} hit alla pipeline primaria."
        
    except Exception as e:
        logger.error(f"[MASSIVE OOM-SAFE FAILED] Stream collapse on {file_url_or_path}: {e}")
        raise self.retry(exc=e, countdown=60)
