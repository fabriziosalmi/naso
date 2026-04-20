import logging
import math

from sqlalchemy import func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from ...models import Identity, LeakHit, identity_leaks

logger = logging.getLogger("naso-risk-scoring")


class IdentityRiskScoringService:
    """
    Algoritmo Avanzato per il calcolo del Rischio Dinamico (#12).
    """

    @classmethod
    async def calculate_and_update_risk(cls, db: AsyncSession, identity_id: str):
        """
        Ricalcola il risk_score tramite aggregazione SQL (P-03).
        Formula: (avg_severity * 0.6) + (log2(count+1) * 15), capped at 100.

        P-03: una singola query SQL AVG+COUNT sostituisce il fetch di tutte le righe
        in Python — O(1) round-trip invece di O(n) rows trasferiti sul wire.
        """
        # P-03: calcola avg e count in un'unica query aggregata lato DB
        agg_query = (
            select(
                func.avg(LeakHit.severity_score).label("avg_sev"),
                func.count(LeakHit.id).label("cnt"),
            )
            .join(identity_leaks, LeakHit.id == identity_leaks.c.leak_id)
            .where(identity_leaks.c.identity_id == identity_id)
        )
        row = (await db.execute(agg_query)).first()

        if not row or not row.cnt:
            return 0

        avg_severity = float(row.avg_sev or 0)
        leak_count = int(row.cnt)

        frequency_bonus = math.log2(leak_count + 1) * 15
        final_score = min(100, round((avg_severity * 0.6) + frequency_bonus))

        # Update Identity risk_score
        identity_result = await db.execute(select(Identity).where(Identity.id == identity_id))
        identity = identity_result.scalar_one_or_none()

        if identity:
            old_score = identity.risk_score
            identity.risk_score = final_score
            await db.flush()
            logger.info(
                f"[RISK SCORING] Identity {identity.identifier} updated: {old_score} -> {final_score} (Leaks: {leak_count})"
            )

        return final_score
