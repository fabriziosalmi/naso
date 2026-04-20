import logging
import os
import re
from uuid import uuid4

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from ...models import Identity, LeakHit, User, identity_leaks
from .mitre import MitreMappingService
from .risk_scoring import IdentityRiskScoringService
from .webhooks import WebhookService

logger = logging.getLogger("naso-correlation")

# P-14: read once at import time — not on every hot-path call via os.getenv()
_CRITICAL_THRESHOLD: int = int(os.getenv("CRITICAL_SCORE_THRESHOLD", "80"))


class IdentityCorrelationService:
    """
    Servizio di Dominio per la Correlazione delle Identità (Command Side).
    Estrae identità dai leak e aggiorna l'Identity Graph.
    """

    # Regex SOTA per estrazione identità
    EMAIL_REGEX = r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}"

    @classmethod
    async def correlate_leak(
        cls,
        db: AsyncSession,
        leak_id: str,
        content: str,
        tenant_id: str,
        screenshot_path: str = None,
        preextracted_emails: set = None,  # P-08: reuse Babel output, skip duplicate regex scan
        severity_score: int = None,        # P-13: avoid DB re-query for leak severity
        leak_source: str = None,           # P-13: avoid DB re-query for leak source
    ):
        # 1. Estrazione Identità — usa output Babel se già disponibile (P-08)
        emails = preextracted_emails if preextracted_emails else set(re.findall(cls.EMAIL_REGEX, content))

        if not emails:
            await MitreMappingService.map_leak_to_ttp(db, leak_id, content)
            await db.commit()
            return

        # 2. Batch fetch di TUTTE le identità esistenti in UNA query IN (P-02)
        # Sostituisce N SELECT sequenziali (uno per email) con un singolo round-trip.
        result = await db.execute(
            select(Identity).where(Identity.identifier.in_(emails), Identity.tenant_id == tenant_id)
        )
        existing_map = {i.identifier: i for i in result.scalars().all()}

        # 3. Batch insert identità mancanti — un solo db.flush() (P-02)
        new_identities: list[Identity] = []
        for email in emails - existing_map.keys():
            identity = Identity(
                id=str(uuid4()),
                tenant_id=tenant_id,
                identifier=email,
                type="email",
                risk_score=50,
            )
            db.add(identity)
            new_identities.append(identity)
        if new_identities:
            await db.flush()  # materializza gli ID senza commit

        all_identities = list(existing_map.values()) + new_identities
        protected_emails = {i.identifier for i in all_identities if i.is_protected}

        # 4. Batch check associazioni — una query IN per tutti gli identity_id (P-02)
        # Sostituisce N SELECT sulla tabella di join (uno per identità).
        existing_assocs = await db.execute(
            select(identity_leaks.c.identity_id).where(
                identity_leaks.c.leak_id == leak_id,
                identity_leaks.c.identity_id.in_([i.id for i in all_identities]),
            )
        )
        already_linked = {row[0] for row in existing_assocs.all()}

        for identity in all_identities:
            if identity.id not in already_linked:
                await db.execute(identity_leaks.insert().values(identity_id=identity.id, leak_id=leak_id))

        # 4.1 Ricalcolo Rischio Dinamico — FUORI dal loop per email (P-03)
        # Precedentemente chiamato N volte dentro il loop; ora chiamato una volta per identità
        # dopo che tutti gli insert sono completati (nessuna ripetizione su entità parziali).
        for identity in all_identities:
            await IdentityRiskScoringService.calculate_and_update_risk(db, identity.id)

        # 4.2 Mitre ATT&CK Mapping (CC)
        await MitreMappingService.map_leak_to_ttp(db, leak_id, content)

        await db.commit()

        # 5. Notifica — usa severity/source passati dall'upstream, zero DB re-query (P-13)
        effective_severity = severity_score if severity_score is not None else 0
        effective_source = leak_source or "unknown"

        if effective_severity >= _CRITICAL_THRESHOLD:
            await cls.notify_critical_hits(
                db, tenant_id, effective_source, effective_severity, emails, is_priority=False
            )
            await WebhookService.trigger_critical_leak(
                db, tenant_id, {"id": leak_id, "source": effective_source, "severity": effective_severity}
            )
        elif protected_emails:
            await cls.notify_critical_hits(
                db, tenant_id, effective_source, effective_severity, protected_emails, is_priority=True
            )
            await WebhookService.trigger_critical_leak(
                db, tenant_id, {"id": leak_id, "source": f"[VIP] {effective_source}", "severity": effective_severity}
            )

    @classmethod
    async def notify_critical_hits(
        cls,
        db: AsyncSession,
        tenant_id: str,
        leak_source: str,
        severity: int,
        emails: set,
        is_priority: bool = False,
    ):
        """
        Un digest per admin, non N×M email per (identità × admin) (P-11).
        Collassa l'intero set di identità compromesse in un singolo alert per destinatario.
        """
        user_result = await db.execute(select(User).where(User.tenant_id == tenant_id, User.role == "admin"))
        admins = user_result.scalars().all()

        if not admins:
            return

        from ...utils.notifications import NotificationService

        # P-11: una sola email per admin con tutte le identità — non N×M SMTP connections
        summary = list(emails)[0] if len(emails) == 1 else f"{len(emails)} identities compromised"
        for admin in admins:
            NotificationService.send_breach_alert(
                recipient_email=admin.email,
                identity_identifier=summary,
                leak_source=leak_source,
                severity=severity,
                is_priority=is_priority,
            )
