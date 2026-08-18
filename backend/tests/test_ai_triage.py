"""The AI triage verdict must reflect what the model said.

`analyze_leak_with_gemma_thinking` asks the model for `VALID: YES` or
`VALID: NO`. It used to compute `is_valid = "valid" in answer.lower()`, and both
answers contain the label "VALID:", so is_valid was True for every leak the
model ever assessed — including the ones it judged NOT a leak. The first fix
replaced that with a strict regex, which had the inverse failure modes:
markdown or bracket decoration ("**VALID:** YES", "VALID: [YES]" — the prompt
template itself displays the format as "VALID: [YES/NO]") parsed as NO, and a
`<think>` block the piped-tag stripper didn't recognize let a hypothetical
"VALID: YES" inside the reasoning override the model's final "VALID: NO".

These tests stub the HTTP call and pin all three properties: the verdict
tracks the model's YES/NO, decoration doesn't flip it, and the LAST verdict
token wins over speculation in an unstripped thought.

They also neutralize the inference gate: these are unit tests, and the real
gate would connect to redis://naso-cache and take the PRODUCTION inference
lock while the suite runs in the API container.
"""

import contextlib

import pytest

import shared.utils.ai_triage as triage


@pytest.fixture(autouse=True)
def _no_real_gate(monkeypatch):
    """Never let a unit test queue on (or hold) the system-wide gate."""

    @contextlib.asynccontextmanager
    async def _null_gate(*_args, **_kwargs):
        yield

    monkeypatch.setattr(triage, "ai_inference_gate", _null_gate)


class _FakeResponse:
    def __init__(self, content):
        self._content = content

    def raise_for_status(self):
        return None

    def json(self):
        return {"choices": [{"message": {"content": self._content}}]}


@pytest.fixture
def stub_model(monkeypatch):
    """Make the module's ai_client.post return a canned model completion."""

    def _install(content):
        async def _post(*_args, **_kwargs):
            return _FakeResponse(content)

        monkeypatch.setattr(triage.ai_client, "post", _post)

    return _install


@pytest.mark.asyncio
async def test_valid_no_is_not_valid(stub_model):
    stub_model("VALID: NO\nSEVERITY: 10\nCATEGORY: OTHER\nRATIONALE: just marketing copy.")
    result = await triage.analyze_leak_with_gemma_thinking("nothing sensitive here")
    assert result["is_valid"] is False


@pytest.mark.asyncio
async def test_valid_yes_is_valid(stub_model):
    stub_model("VALID: YES\nSEVERITY: 95\nCATEGORY: CREDENTIALS\nRATIONALE: email:password pairs.")
    result = await triage.analyze_leak_with_gemma_thinking("bob@corp.example:hunter2")
    assert result["is_valid"] is True


@pytest.mark.asyncio
async def test_piped_thinking_tags_are_stripped_from_the_answer(stub_model):
    stub_model("<|think|>let me reason<|/think|>VALID: NO\nSEVERITY: 0")
    result = await triage.analyze_leak_with_gemma_thinking("x")
    assert result["thought"] == "let me reason"
    assert "<|think|>" not in result["answer"]
    assert result["is_valid"] is False


@pytest.mark.asyncio
async def test_qwen_style_thinking_tags_are_stripped_too(stub_model):
    # Qwen-family models (the .env default) emit <think>...</think> without
    # pipes. A hypothetical "VALID: YES" inside that reasoning must not
    # override the model's final "VALID: NO".
    stub_model(
        "<think>If these were real credentials I would answer VALID: YES. "
        "But every address is an example.com placeholder.</think>\n"
        "VALID: NO\nSEVERITY: 5"
    )
    result = await triage.analyze_leak_with_gemma_thinking("user@example.com:test123")
    assert result["thought"].startswith("If these were real")
    assert "<think>" not in result["answer"]
    assert result["is_valid"] is False


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("completion", "expected"),
    [
        ("**VALID:** YES\nSEVERITY: 95", True),
        ("VALID: **YES**\nSEVERITY: 95", True),
        ("VALID: [YES]\nSEVERITY: 95", True),  # the template literally shows "VALID: [YES/NO]"
        ("**VALID:** NO\nSEVERITY: 5", False),
        ("VALID: [NO]\nSEVERITY: 5", False),
    ],
)
async def test_decorated_verdicts_still_parse(stub_model, completion, expected):
    stub_model(completion)
    result = await triage.analyze_leak_with_gemma_thinking("x")
    assert result["is_valid"] is expected


@pytest.mark.asyncio
async def test_last_verdict_token_wins_over_earlier_speculation(stub_model):
    # Even when reasoning survives the tag strip (unclosed/unknown tags),
    # the model's conclusion is the LAST verdict line, not the first mention.
    stub_model("Considering whether VALID: YES applies here... no.\nVALID: NO\nSEVERITY: 5")
    result = await triage.analyze_leak_with_gemma_thinking("x")
    assert result["is_valid"] is False


def test_normalize_ai_analysis_accepts_all_shapes():
    # Producer shape, seeder shape, legacy junk — one accessor for every
    # consumer (the /intelligence endpoint and the PDF report), so ai_verdict
    # is always a string or None, never the raw dict.
    assert triage.normalize_ai_analysis({"thought": "t", "answer": "a", "is_valid": True}) == ("t", "a")
    assert triage.normalize_ai_analysis({"is_valid": True}) == (None, None)
    assert triage.normalize_ai_analysis("plain seeder verdict") == (None, "plain seeder verdict")
    assert triage.normalize_ai_analysis(None) == (None, None)
    assert triage.normalize_ai_analysis("") == (None, None)
