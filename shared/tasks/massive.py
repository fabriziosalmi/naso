import logging
import re
from urllib.parse import urlparse

import requests

from shared.celery_app import celery_app
from shared.tasks.pipeline import process_potential_leak

logger = logging.getLogger("naso-massive")

# Espressioni regolari per identificare criticità in log massicci
EMAIL_REGEX = re.compile(r"[a-z0-9\.\-+_]+@[a-z0-9\.\-+_]+\.[a-z]+", re.I)
PRIVATE_KEY_REGEX = re.compile(r"-----BEGIN (RSA|OPENSSH) PRIVATE KEY-----")

# Limite di dimensione per singola riga (evita OOM su righe malformate)
MAX_LINE_BYTES = 1024 * 64  # 64 KB

# P-12: batch N righe in un singolo task Celery invece di 1 task per riga.
# 1 task per riga su un dump da 5M righe = 5M messaggi RabbitMQ + 5M DB connections.
BATCH_SIZE = 100


def _flush_batch(batch: list[str], tenant_id: str, source: str, up_to_line: int) -> None:
    """Dispatch a batch of suspicious lines into the pipeline as a single task."""
    hit_data = {
        "tenant_id": tenant_id,
        "source": f"Massive Dump Stream: {source}",
        "metadata_json": {"up_to_line": up_to_line, "engine": "Naso-Stream-Processor", "batch_size": len(batch)},
    }
    combined = "\n".join(batch)
    process_potential_leak.apply_async((hit_data, combined), queue="default")


def _open_stream(file_url_or_path: str):
    """
    Return an iterator of lines (str) from a local path or an HTTP/HTTPS URL.
    Non carica mai l'intero file in memoria.
    """
    parsed = urlparse(file_url_or_path)
    if parsed.scheme in ("http", "https"):
        resp = requests.get(file_url_or_path, stream=True, timeout=30)
        resp.raise_for_status()
        return resp.iter_lines(decode_unicode=True)
    else:
        # Path locale — supporta sia path assoluti che relativi
        return open(file_url_or_path, encoding="utf-8", errors="replace")  # noqa: SIM115


@celery_app.task(bind=True, max_retries=1, queue="massive", name="tasks.massive.process_blob_stream")
def process_blob_stream(self, file_url_or_path: str, tenant_id: str):
    """
    Streaming Processor OOM-safe.
    Reads a gigabyte-scale dump line by line from a local file or an HTTP/HTTPS URL.
    Applies a fast regex pass and forwards only the relevant chunks to the pipeline.
    """
    stream = None
    try:
        logger.info(f"[MASSIVE INGESTION] Starting OOM-safe stream for: {file_url_or_path}")

        suspicious_chunks_found = 0
        total_lines_read = 0
        _batch: list[str] = []

        stream = _open_stream(file_url_or_path)

        for line in stream:
            # Truncate abnormally long lines to keep the AI worker from running out of memory
            if len(line) > MAX_LINE_BYTES:
                line = line[:MAX_LINE_BYTES]

            total_lines_read += 1

            if EMAIL_REGEX.search(line) or PRIVATE_KEY_REGEX.search(line):
                suspicious_chunks_found += 1
                _batch.append(line)
                # P-12: dispatch in batch, not one task per line
                if len(_batch) >= BATCH_SIZE:
                    _flush_batch(_batch, tenant_id, file_url_or_path, total_lines_read)
                    _batch = []

        # Flush remaining partial batch
        if _batch:
            _flush_batch(_batch, tenant_id, file_url_or_path, total_lines_read)

        logger.info(
            f"[MASSIVE INGESTION] Complete. Lines read: {total_lines_read}. "
            f"Suspicious hits delegated: {suspicious_chunks_found}."
        )
        return f"Processed {file_url_or_path} - delegated {suspicious_chunks_found} hits to the primary pipeline."

    except Exception as e:
        logger.error(f"[MASSIVE OOM-SAFE FAILED] Stream collapse on {file_url_or_path}: {e}")
        raise self.retry(exc=e, countdown=60)
    finally:
        if stream is not None and hasattr(stream, "close"):
            stream.close()
