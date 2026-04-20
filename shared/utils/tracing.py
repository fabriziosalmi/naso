"""OpenTelemetry helpers for the NASO backend.

Two concerns live here:

    1. A single ``get_tracer()`` accessor so callers share a tracer
       instance (``"naso.ai"`` as the instrumentation name).
    2. A ``tool_span`` context manager used by the agent loop to open
       one span per tool call with a consistent attribute shape. That
       shape is what Grafana / Jaeger dashboards will query by, so keep
       it frozen: tool.name, naso.tenant_id, naso.user_id,
       naso.investigation_id, naso.parallel, naso.ai_iteration, and
       naso.result.error / naso.cache.hit set at exit time.

Toggle: ``NASO_OTEL_ENABLED`` env var. When false (default), ``tool_span``
returns a ``nullcontext`` so no dict allocation, no attribute copies,
no span.end() — the hot path pays zero cost.

No-SDK fallback: even when ``NASO_OTEL_ENABLED=true``, if the SDK
provider has not been registered (tests, scripts), OTel's API layer
returns the built-in NoOpTracer so nothing crashes.
"""
from __future__ import annotations

import contextlib
import os
from typing import Any

try:
    from opentelemetry import trace
    from opentelemetry.trace import Status, StatusCode
    _OTEL_AVAILABLE = True
except ImportError:  # pragma: no cover — opentelemetry-api is in requirements
    _OTEL_AVAILABLE = False

# Evaluated once at import so toggling it at runtime requires a restart
# (standard OTel deployment pattern).
_OTEL_ENABLED = os.getenv("NASO_OTEL_ENABLED", "").strip().lower() in {"1", "true", "yes", "on"}


def is_enabled() -> bool:
    """Public view of the toggle state — useful in tests and debug logs."""
    return _OTEL_ENABLED and _OTEL_AVAILABLE


_TRACER = None


def get_tracer():
    """Return the shared naso.ai tracer. No-op when OTel is disabled."""
    global _TRACER
    if not is_enabled():
        return None
    if _TRACER is None:
        _TRACER = trace.get_tracer("naso.ai")
    return _TRACER


@contextlib.contextmanager
def tool_span(
    tool_name: str,
    *,
    tenant_id: str | None = None,
    user_id: str | None = None,
    investigation_id: str | None = None,
    parallel: bool = False,
    ai_iteration: int = 0,
):
    """Open a span for one AI tool call. Yields the span (or ``None`` when
    OTel is disabled) so callers can add attributes at exit time.

    Span name: ``naso.ai_tool.<tool_name>``. The name is separately queryable
    from the ``tool.name`` attribute because span-name indexing works
    differently from attribute indexing in most backends — having both is
    deliberate.

    Attributes with ``None`` values are omitted to keep span payloads
    small.
    """
    if not is_enabled():
        yield None
        return

    tracer = get_tracer()
    attrs: dict[str, Any] = {
        "tool.name": tool_name,
        "naso.parallel": parallel,
        "naso.ai_iteration": int(ai_iteration),
    }
    if tenant_id is not None:
        attrs["naso.tenant_id"] = str(tenant_id)
    if user_id is not None:
        attrs["naso.user_id"] = str(user_id)
    if investigation_id is not None:
        attrs["naso.investigation_id"] = str(investigation_id)

    with tracer.start_as_current_span(f"naso.ai_tool.{tool_name}", attributes=attrs) as span:
        try:
            yield span
        except Exception as exc:
            # Record the exception and mark the span errored before letting
            # it propagate. Callers are still free to catch downstream.
            span.record_exception(exc)
            span.set_status(Status(StatusCode.ERROR, str(exc)[:200]))
            raise


@contextlib.contextmanager
def agent_turn_span(*, iteration: int, tenant_id: str | None = None):
    """Parent span for one iteration of the agent loop. Tool spans created
    inside it automatically become children via the current-span context.
    """
    if not is_enabled():
        yield None
        return

    tracer = get_tracer()
    attrs = {"naso.ai_iteration": int(iteration)}
    if tenant_id is not None:
        attrs["naso.tenant_id"] = str(tenant_id)
    with tracer.start_as_current_span("naso.ai_agent.turn", attributes=attrs) as span:
        yield span


def annotate_result(span, result: dict[str, Any] | None) -> None:
    """Set span attributes based on the tool's return value.

    * ``naso.result.error`` — present and truncated to 200 chars when the
      tool returned an error payload.
    * ``naso.cache.hit`` — set when dark_web_probe's result was served
      from the AhmiaClient cache.

    ``span=None`` (OTel disabled) → no-op.
    """
    if span is None or not isinstance(result, dict):
        return
    err = result.get("error")
    if err:
        span.set_attribute("naso.result.error", str(err)[:200])
        try:
            span.set_status(Status(StatusCode.ERROR))
        except Exception:
            pass
    if result.get("cached") is True:
        span.set_attribute("naso.cache.hit", True)


__all__ = [
    "is_enabled",
    "get_tracer",
    "tool_span",
    "agent_turn_span",
    "annotate_result",
]
