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
    """Exception raised when the AI service fails."""

    pass


@retry(
    stop=stop_after_attempt(5),
    wait=wait_exponential_jitter(initial=1, max=10),  # Exponential Backoff with Jitter (#3)
    retry=retry_if_exception_type(httpx.RequestError),
    reraise=True,
)
async def analyze_leak_with_gemma_thinking(content_snippet):
    """
    Use Gemma 4's reasoning to validate a leak.
    Implements graceful degradation (#15): if the AI fails after the retries,
    the leak is downgraded rather than blocking the pipeline.
    """
    # P-09: truncation is the caller's responsibility (raw_content[:2500] in pipeline.py).
    # Receiving an already-trimmed snippet here avoids allocating a 1MB string argument.
    prompt = f"""
    NASO FORENSIC ANALYSIS v1.0
    Role: Threat Intelligence & Data Breach Analyst
    Task: assess whether the following content is a leak of REAL sensitive data.

    VALIDATION CRITERIA:
    - Presence of credentials (email:password)
    - Financial data (credit cards, IBAN)
    - PII (identity documents, addresses, phone numbers)
    - Proprietary source code or secrets (API keys)

    Answer in exactly this format:
    VALID: [YES/NO]
    SEVERITY: [0-100]
    CATEGORY: [CREDENTIALS/FINANCIAL/PII/SOURCE/OTHER]
    RATIONALE: brief technical explanation.

    CONTENT:
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
