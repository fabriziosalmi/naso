"""Shared exception types for the correlation domain.

Kept in their own module so services can raise them and callers (HTTP
handlers, AI tools, Celery workers) can catch them without creating an
import cycle with the service modules themselves.
"""

from __future__ import annotations


class CorrelationError(Exception):
    """Base class for every deterministic failure in the correlation engine."""


class InsufficientEvidence(CorrelationError):
    """Raised by ``merge_identities`` when the supplied evidence does not
    reach the minimum aggregate confidence. The engine never guesses — it
    tells the caller the threshold was not met.
    """


class CrossTenantMerge(CorrelationError):
    """Raised when a merge is attempted across two tenants. Tenant isolation
    is a hard invariant; crossing it would leak data between customers.
    """


class VipInvariantViolation(CorrelationError):
    """Raised when a merge would silently demote a protected identity.

    Policy: when a VIP slave is proposed under an unprotected master, the
    engine promotes the master to VIP (see
    :func:`shared.domain.services.entity_resolution.merge_identities`). If a
    future policy forbids promotion (e.g. role-gated), the merge is refused
    with this exception instead.
    """


__all__ = [
    "CorrelationError",
    "InsufficientEvidence",
    "CrossTenantMerge",
    "VipInvariantViolation",
]
