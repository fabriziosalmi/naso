import logging
import os
import re

import httpx
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential_jitter

logger = logging.getLogger("naso-ai")

AI_URL = os.getenv("AI_ENDPOINT", "http://host.docker.internal:1234/v1")
MODEL = os.getenv("AI_MODEL", "google/gemma-4-E2B-it")

# Global HTTP client for persistent connection pooling (Mission Critical Performance)
ai_client = httpx.AsyncClient(timeout=90.0, limits=httpx.Limits(max_keepalive_connections=20, max_connections=50))


class AIServiceError(Exception):
    """Eccezione specifica per fallimenti del servizio AI."""

    pass


@retry(
    stop=stop_after_attempt(5),
    wait=wait_exponential_jitter(initial=1, max=10),  # Exponential Backoff with Jitter (#3)
    retry=retry_if_exception_type(httpx.RequestError),
    reraise=True,
)
async def analyze_leak_with_gemma_thinking(content_snippet):
    """
    Sfrutta il ragionamento di Gemma 4 per validare i leak.
    Implementa Graceful Degradation (#15): se l'AI fallisce dopo i retry,
    il sistema declassa il leak ma non blocca la pipeline.
    """
    # P-09: truncation is the caller's responsibility (raw_content[:2500] in pipeline.py).
    # Receiving an already-trimmed snippet here avoids allocating a 1MB string argument.
    prompt = f"""
    ANALISI FORENSE NASO v1.0
    Ruolo: Esperto Threat Intelligence & Data Breach Analyst
    Task: Valuta se il contenuto seguente è un leak di dati sensibili REALI.
    
    CRITERI DI VALIDAZIONE:
    - Presenza di credenziali (email:password)
    - Dati finanziari (CC, IBAN)
    - Dati PII (Documenti, Indirizzi, Telefoni)
    - Codice sorgente proprietario o segreti (API Keys)
    
    Rispondi in questo formato:
    VALIDO: [SI/NO]
    SEVERITA: [0-100]
    CATEGORIA: [CREDENTIALS/FINANCIAL/PII/SOURCE/OTHER]
    MOTIVAZIONE: Breve spiegazione tecnica.
    
    CONTENUTO:
    {content_snippet}
    """
    messages = [{"role": "user", "content": prompt}]

    try:
        response = await ai_client.post(
            f"{AI_URL}/chat/completions",
            json={"model": MODEL, "messages": messages, "extra_body": {"enable_thinking": True}, "temperature": 0.1},
        )
        response.raise_for_status()

        full_response = response.json()["choices"][0]["message"]["content"]
        thought = ""
        answer = full_response
        # Match Gemma/Qwen thinking tags: <|think|>...</|think|>
        thought_match = re.search(r"<\|think\|>(.*?)<\|/think\|>", full_response, re.DOTALL)
        if thought_match:
            thought = thought_match.group(1).strip()
            answer = full_response.replace(thought_match.group(0), "").strip()
        return {"thought": thought, "answer": answer, "is_valid": "vero" in answer.lower() or "valid" in answer.lower()}
    except Exception as e:
        # Graceful Degradation (#15)
        logger.warning(f"[GRACEFUL DEGRADATION] AI Service Unavailable: {e}")
        raise AIServiceError(f"AI Connection failed: {e}")
