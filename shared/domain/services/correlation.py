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


class IdentityCorrelationService:
    """
    Servizio di Dominio per la Correlazione delle Identità (Command Side).
    Estrae identità dai leak e aggiorna l'Identity Graph.
    """

    # Regex SOTA per estrazione identità
    EMAIL_REGEX = r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}"

    @classmethod
    async def correlate_leak(
        cls, db: AsyncSession, leak_id: str, content: str, tenant_id: str, screenshot_path: str = None
    ):
        # 1. Estrazione Identità (Email per ora)
        emails = set(re.findall(cls.EMAIL_REGEX, content))
        protected_emails = set()

        for email in emails:
            # 2. Cerca se l'identità esiste già per il tenant
            result = await db.execute(
                select(Identity).where(Identity.identifier == email, Identity.tenant_id == tenant_id)
            )
            identity = result.scalar_one_or_none()

            if not identity:
                # 3. Crea nuova identità se non esiste
                identity = Identity(
                    id=str(uuid4()),
                    tenant_id=tenant_id,
                    identifier=email,
                    type="email",
                    risk_score=50,  # Score base
                )
                db.add(identity)
                await db.flush()  # Ottieni l'ID senza commit totale

            if identity.is_protected:
                protected_emails.add(email)

            # 4. Collega l'identità al leak (Associazione Idempotente)
            # Usiamo una query diretta sulla tabella di associazione per evitare duplicati
            assoc_check = await db.execute(
                select(identity_leaks).where(
                    identity_leaks.c.identity_id == identity.id, identity_leaks.c.leak_id == leak_id
                )
            )
            if not assoc_check.first():
                await db.execute(identity_leaks.insert().values(identity_id=identity.id, leak_id=leak_id))

            # 4.1 Ricalcolo Rischio Dinamico (#12)
            await IdentityRiskScoringService.calculate_and_update_risk(db, identity.id)

        # 4.2 Mitre ATT&CK Mapping (CC)
        await MitreMappingService.map_leak_to_ttp(db, leak_id, content)

        await db.commit()

        # 5. Notifica Automatica per Leak Critici (#9) o Identità Protette (#11)
        severity_threshold = int(os.getenv("CRITICAL_SCORE_THRESHOLD", 80))
        leak_result = await db.execute(select(LeakHit).where(LeakHit.id == leak_id))
        leak = leak_result.scalar_one_or_none()

        if leak:
            # Notifichiamo se il leak è critico O se abbiamo colpito identità protette
            if leak.severity_score >= severity_threshold:
                await cls.notify_critical_hits(db, leak, emails, is_priority=False)
                # Trigger Webhooks (U)
                await WebhookService.trigger_critical_leak(
                    db, tenant_id, {"id": leak.id, "source": leak.source, "severity": leak.severity_score}
                )
            elif protected_emails:
                await cls.notify_critical_hits(db, leak, protected_emails, is_priority=True)
                # Trigger Webhooks per VIP
                await WebhookService.trigger_critical_leak(
                    db, tenant_id, {"id": leak.id, "source": f"[VIP] {leak.source}", "severity": leak.severity_score}
                )

    @classmethod
    async def notify_critical_hits(cls, db: AsyncSession, leak: LeakHit, emails: set, is_priority: bool = False):
        """
        Invia notifiche per i colpi critici o identità protette.
        """
        user_result = await db.execute(select(User).where(User.tenant_id == leak.tenant_id, User.role == "admin"))
        admins = user_result.scalars().all()

        if not admins:
            return

        from ...utils.notifications import NotificationService

        for identifier in emails:
            for admin in admins:
                NotificationService.send_breach_alert(
                    recipient_email=admin.email,
                    identity_identifier=identifier,
                    leak_source=leak.source,
                    severity=leak.severity_score,
                    is_priority=is_priority,  # Passiamo il flag di priorità
                )
