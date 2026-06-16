"""Tracing helper + toggle behavior.

We do not spin up an OTel SDK / exporter in tests — the goal is to
verify:
    * ``is_enabled()`` reflects the env toggle.
    * ``tool_span`` and ``agent_turn_span`` are no-ops when disabled
      (yield ``None``, no exceptions).
    * ``annotate_result`` handles a ``None`` span gracefully.
    * When the toggle is on, ``tool_span`` yields a real span object
      (the API-layer NoOpSpan is still an object that supports
      set_attribute / set_status without a registered SDK).
"""

from __future__ import annotations

import importlib

from shared.utils import tracing


def _reload(monkeypatch, *, enabled: bool) -> None:
    """Toggle the env var and reload the module so the import-time
    ``_OTEL_ENABLED`` constant re-evaluates.
    """
    monkeypatch.setenv("NASO_OTEL_ENABLED", "true" if enabled else "false")
    # _TRACER is cached at module scope; reloading clears it along with
    # the toggle.
    importlib.reload(tracing)


class TestToggle:
    def test_disabled_by_default(self, monkeypatch):
        monkeypatch.delenv("NASO_OTEL_ENABLED", raising=False)
        importlib.reload(tracing)
        assert tracing.is_enabled() is False

    def test_enabled_with_true(self, monkeypatch):
        _reload(monkeypatch, enabled=True)
        assert tracing.is_enabled() is True

    def test_various_truthy_values_accepted(self, monkeypatch):
        for val in ["1", "true", "TRUE", "yes", "on"]:
            monkeypatch.setenv("NASO_OTEL_ENABLED", val)
            importlib.reload(tracing)
            assert tracing.is_enabled(), f"expected enabled for {val!r}"


class TestDisabledPath:
    def test_tool_span_yields_none(self, monkeypatch):
        _reload(monkeypatch, enabled=False)
        with tracing.tool_span("my_tool", tenant_id="t", user_id="u") as span:
            assert span is None

    def test_agent_turn_span_yields_none(self, monkeypatch):
        _reload(monkeypatch, enabled=False)
        with tracing.agent_turn_span(iteration=0, tenant_id="t") as span:
            assert span is None

    def test_annotate_result_handles_none_span(self, monkeypatch):
        _reload(monkeypatch, enabled=False)
        # Must not raise even with a populated result dict.
        tracing.annotate_result(None, {"tool": "x", "error": "boom", "cached": True})


class TestEnabledPath:
    """When OTel is enabled but no SDK is registered, the API returns
    a NoOp tracer whose spans are still well-behaved objects. These
    tests verify the wiring compiles end-to-end under the toggle.
    """

    def test_tool_span_yields_span_object(self, monkeypatch):
        _reload(monkeypatch, enabled=True)
        with tracing.tool_span(
            "my_tool",
            tenant_id="t",
            user_id="u",
            investigation_id="inv",
            parallel=True,
            ai_iteration=3,
        ) as span:
            assert span is not None
            # No-op spans accept set_attribute without error.
            span.set_attribute("naso.test", "ok")

    def test_agent_turn_span_yields_span_object(self, monkeypatch):
        _reload(monkeypatch, enabled=True)
        with tracing.agent_turn_span(iteration=1, tenant_id="t") as span:
            assert span is not None

    def test_annotate_result_error_path(self, monkeypatch):
        _reload(monkeypatch, enabled=True)
        with tracing.tool_span("my_tool") as span:
            tracing.annotate_result(span, {"tool": "my_tool", "error": "something failed"})
            # Span accepts the attributes; no exception raised.

    def test_annotate_result_cached_path(self, monkeypatch):
        _reload(monkeypatch, enabled=True)
        with tracing.tool_span("dark_web_probe") as span:
            tracing.annotate_result(span, {"tool": "dark_web_probe", "cached": True, "count": 3})
