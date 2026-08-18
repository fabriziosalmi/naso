import logging
import re

import httpx
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential_jitter

from shared.config import settings
from shared.utils.ai_gate import ai_inference_gate

logger = logging.getLogger("naso-ai")

# No keepalive: Celery runs each task on a fresh event loop
# (asyncio.new_event_loop in pipeline.py), and a kept-alive connection is
# bound to the loop that opened it — reusing it from the next task's loop
# raises "Event loop is closed". With the inference gate serializing every
# call anyway, connection reuse buys nothing.
ai_client = httpx.AsyncClient(timeout=90.0, limits=httpx.Limits(max_keepalive_connections=0, max_connections=50))

# Local models wrap their reasoning in thinking tags before the actual
# answer. Which tags depends on the model family: Qwen-style emits
# <think>...</think>, some Gemma builds emit <|think|>...<|/think|>.
# Match both — an unstripped thought means the verdict gets parsed out of
# the model's speculation instead of its conclusion.
_THINK_RE = re.compile(r"<\|think\|>(.*?)<\|/think\|>|<think>(.*?)</think>", re.DOTALL)

# The verdict token, tolerant of the decoration chat-tuned models add:
# "VALID: YES", "**VALID:** YES", "VALID: [YES]" (the prompt template
# literally displays the format as "VALID: [YES/NO]") all must parse.
# \bVALID\b keeps "INVALID" from matching; \W{0,8} spans the colon plus
# any markdown/bracket noise between label and token.
_VERDICT_RE = re.compile(r"\bVALID\b\W{0,8}(YES|NO|SI|SÌ|VERO|FALSO|TRUE|FALSE)\b", re.IGNORECASE)

_YES_TOKENS = {"YES", "SI", "SÌ", "VERO", "TRUE"}


def normalize_ai_analysis(value):
    """Return ``(thought, verdict)`` from a ``metadata_json['ai_analysis']`` payload.

    The pipeline writes ``{thought, answer, is_valid}``; the demo seeder
    writes a plain string; legacy rows may hold anything. Every consumer
    (the /intelligence endpoint, the PDF report) goes through here so the
    shape knowledge lives once, next to the producer.
    """
    if isinstance(value, dict):
        return (value.get("thought") or None, value.get("answer") or None)
    if value:
        return (None, str(value))
    return (None, None)


class AIServiceError(Exception):
    """Exception raised when the AI service fails."""

    pass


# Retry ONLY fast connect-level failures (LM Studio restarting, socket not yet
# listening): a refused connection costs milliseconds, so five attempts with
# jitter stay near-instant. Read timeouts must NOT retry — each one costs the
# full 90s HTTP budget plus a fresh gate wait, and five of those blow through
# Celery's 300s hard kill. This decorator was previously dead code: it matched
# httpx.RequestError, but the function's own `except Exception` converted every
# exception into AIServiceError before the predicate could ever see it.
@retry(
    stop=stop_after_attempt(5),
    wait=wait_exponential_jitter(initial=1, max=10),  # Exponential Backoff with Jitter (#3)
    retry=retry_if_exception_type(httpx.ConnectError),
    reraise=True,
)
async def analyze_leak_with_gemma_thinking(content_snippet):
    """
    Use the local model's reasoning to validate a leak.
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
        # One inference at a time system-wide: LM Studio shares the host's
        # memory and concurrent completions have taken the machine down (see
        # shared/utils/ai_gate.py). The acquire budget is tighter than the
        # gate's default: 90s wait + 90s HTTP leaves Celery's 300s hard task
        # limit real headroom for the rest of the pipeline.
        async with ai_inference_gate(acquire_timeout=90.0):
            # Settings, not os.getenv: Settings also reads .env and
            # /run/secrets, and it is what the rest of the stack (and the
            # test suite's monkeypatch pattern) uses. AI_ENABLE_THINKING was
            # previously hardcoded True, silently overriding the operator's
            # configured value.
            response = await ai_client.post(
                f"{settings.AI_ENDPOINT}/chat/completions",
                json={
                    "model": settings.AI_MODEL,
                    "messages": messages,
                    "extra_body": {"enable_thinking": settings.AI_ENABLE_THINKING},
                    "temperature": 0.1,
                },
            )
            response.raise_for_status()

        full_response = response.json()["choices"][0]["message"]["content"]
        thought = ""
        answer = full_response
        thought_match = _THINK_RE.search(full_response)
        if thought_match:
            thought = (thought_match.group(1) or thought_match.group(2) or "").strip()
            answer = full_response.replace(thought_match.group(0), "").strip()
        # Parse the actual verdict, not the substring "valid" (the old
        # `"valid" in answer.lower()` was True for every answer, including
        # "VALID: NO"). The LAST match wins: if any reasoning survives the
        # tag strip, a hypothetical "VALID: YES" mid-deliberation must not
        # override the model's final line.
        tokens = _VERDICT_RE.findall(answer)
        is_valid = bool(tokens) and tokens[-1].upper() in _YES_TOKENS
        return {"thought": thought, "answer": answer, "is_valid": is_valid}
    except httpx.ConnectError:
        # Fast link-level failure — let tenacity's backoff retry it; after the
        # last attempt it propagates and the pipeline degrades as usual.
        raise
    except Exception as e:
        # Graceful Degradation (#15)
        logger.warning(f"[GRACEFUL DEGRADATION] AI Service Unavailable: {e}")
        raise AIServiceError(f"AI Connection failed: {e}")
