import logging

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from ...models import Identity

logger = logging.getLogger("naso-identity-merging")


class IdentityMergingService:
    """
    Algoritmo per l'unione di identità correlate (V).
    """

    @classmethod
    async def auto_merge_identities(cls, db: AsyncSession, tenant_id: str):
        """
        Scansiona le identità del tenant e unisce quelle che condividono pattern comuni
        (es. lo stesso username in email diverse o metadata collegati).
        """
        # Recupera in Lotti (Batch Limit) per prevenire OOM Enterprise (Max 5000)
        result = await db.execute(
            select(Identity).where(Identity.tenant_id == tenant_id, Identity.master_identity_id is None).limit(5000)
        )
        identities = result.scalars().all()

        merged_count = 0

        # Logica SOTA: Raggruppamento per Username Base
        # Esempio: fabrizio@gmail.com e fabrizio@naso.local -> Uniscili sotto un profilo "fabrizio"
        user_map = {}
        for identity in identities:
            username = identity.identifier.split("@")[0].lower()
            if username not in user_map:
                user_map[username] = []
            user_map[username].append(identity)

        for username, related in user_map.items():
            if len(related) > 1:
                # Eleggiamo il primo come master
                master = related[0]
                for slave in related[1:]:
                    slave.master_identity_id = master.id
                    # Somma del rischio (con cap a 100)
                    master.risk_score = min(100, master.risk_score + (slave.risk_score // 2))
                    merged_count += 1
                    logger.info(f"[MERGE] Identity {slave.identifier} merged into {master.identifier}")

        await db.commit()
        return merged_count
