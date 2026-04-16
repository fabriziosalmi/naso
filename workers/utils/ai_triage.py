import httpx
import os
import re
import logging
from tenacity import retry, stop_after_attempt, wait_exponential_jitter, retry_if_exception_type

logger = logging.getLogger("naso-ai")

AI_URL = os.getenv("AI_ENDPOINT", "http://192.168.100.7:1234/v1")
MODEL = os.getenv("AI_MODEL", "google/gemma-4-E2B-it")

# Global HTTP client for persistent connection pooling (Mission Critical Performance)
ai_client = httpx.AsyncClient(timeout=60.0, limits=httpx.Limits(max_keepalive_connections=20, max_connections=50))

class AIServiceError(Exception):
    """Eccezione specifica per fallimenti del servizio AI."""
    pass

@retry(
    stop=stop_after_attempt(5),
    wait=wait_exponential_jitter(initial=1, max=10), # Exponential Backoff with Jitter (#3)
    retry=retry_if_exception_type(httpx.RequestError),
    reraise=True
)
async def analyze_leak_with_gemma_thinking(content_snippet):
    """
    Sfrutta il ragionamento di Gemma 4 per validare i leak.
    Implementa Graceful Degradation (#15): se l'AI fallisce dopo i retry, 
    il sistema declassa il leak ma non blocca la pipeline.
    """
    prompt = f"Analizza questo leak forense. Pensa prima di rispondere. Contiene dati sensibili reali? \n\n {content_snippet[:2000]}"
    messages = [{"role": "user", "content": prompt}]
    
    try:
        response = await ai_client.post(
            f"{AI_URL}/chat/completions",
            json={"model": MODEL, "messages": messages, "extra_body": {"enable_thinking": True}, "temperature": 0.1}
        )
        response.raise_for_status()
        
        full_response = response.json()['choices'][0]['message']['content']
        thought = ""
        answer = full_response
        thought_match = re.search(r'<\|think\|>(.*?)<turn|>', full_response, re.DOTALL)
        if thought_match:
            thought = thought_match.group(1).strip()
            answer = full_response.replace(thought_match.group(0), "").strip()
        return {"thought": thought, "answer": answer, "is_valid": "vero" in answer.lower() or "valid" in answer.lower()}
    except Exception as e:
        # Graceful Degradation (#15)
        logger.warning(f"[GRACEFUL DEGRADATION] AI Service Unavailable: {e}")
        raise AIServiceError(f"AI Connection failed: {e}")
