from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from ...models import Identity, LeakHit, identity_leaks
import logging

logger = logging.getLogger("naso-risk-scoring")

class IdentityRiskScoringService:
    """
    Algoritmo Avanzato per il calcolo del Rischio Dinamico (#12).
    """

    @classmethod
    async def calculate_and_update_risk(cls, db: AsyncSession, identity_id: str):
        """
        Ricalcola il risk_score di un'identità basandosi sulla storia dei leak.
        Formula: (Media Severity * 0.6) + (Log2(Numero Leak) * 20)
        Garantisce che il punteggio sia compreso tra 0 e 100.
        """
        # 1. Recupera tutti i leak associati all'identità
        query = (
            select(LeakHit.severity_score)
            .join(identity_leaks, LeakHit.id == identity_leaks.c.leak_id)
            .where(identity_leaks.c.identity_id == identity_id)
        )
        result = await db.execute(query)
        severities = [r[0] for r in result.all()]
        
        if not severities:
            return 0

        leak_count = len(severities)
        avg_severity = sum(severities) / leak_count
        
        # 2. Logica di Scoring
        # Bonus frequenza: più un'identità appare in leak diversi, più è a rischio
        # Usiamo un moltiplicatore logaritmico per non esplodere
        import math
        frequency_bonus = math.log2(leak_count + 1) * 15
        
        base_score = (avg_severity * 0.6) + frequency_bonus
        
        # 3. Cap a 100
        final_score = min(100, round(base_score))
        
        # 4. Update Identity
        update_query = select(Identity).where(Identity.id == identity_id)
        identity_result = await db.execute(update_query)
        identity = identity_result.scalar_one_or_none()
        
        if identity:
            old_score = identity.risk_score
            identity.risk_score = final_score
            await db.flush()
            
            logger.info(f"[RISK SCORING] Identity {identity.identifier} updated: {old_score} -> {final_score} (Leaks: {leak_count})")
            
        return final_score
