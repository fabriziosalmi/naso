"""The AI triage verdict must reflect what the model said.

`analyze_leak_with_gemma_thinking` asks the model for `VALID: YES` or
`VALID: NO`. It used to compute `is_valid = "valid" in answer.lower()`, and both
answers contain the label "VALID:", so is_valid was True for every leak the
model ever assessed — including the ones it judged NOT a leak. A forensic
validity verdict that is unconditionally positive is the defect here.

These tests stub the HTTP call and assert the parsed verdict tracks the model's
YES/NO, so the regression cannot come back.
"""

import pytest

import shared.utils.ai_triage as triage


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
async def test_thinking_tags_are_stripped_from_the_answer(stub_model):
    stub_model("<|think|>let me reason<|/think|>VALID: NO\nSEVERITY: 0")
    result = await triage.analyze_leak_with_gemma_thinking("x")
    assert result["thought"] == "let me reason"
    assert "<|think|>" not in result["answer"]
    assert result["is_valid"] is False
