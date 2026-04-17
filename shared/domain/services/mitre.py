import logging

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from ...models import MitreTechnique, mitre_leaks

logger = logging.getLogger("naso-mitre")


class MitreMappingService:
    """
    Automated Mitre ATT&CK Mapping (CC).
    Mappa i leak alle tecniche avversarie basandosi sul contenuto e sulla fonte.
    """

    # Mapping Table SOTA (Semplificata per il prototipo)
    KEYWORD_MAPPINGS = {
        "password": ["T1110", "T1555"],  # Brute Force, Credentials from web browsers
        "email": ["T1589"],  # Gather Victim Identity Information
        "config": ["T1608"],  # Stage Capabilities
        "github": ["T1195"],  # Supply Chain Compromise
        "credential": ["T1528"],  # Steal Application Access Token
        "onion": ["T1583"],  # Acquire Infrastructure
    }

    @classmethod
    async def map_leak_to_ttp(cls, db: AsyncSession, leak_id: str, content: str):
        """
        Analizza il leak e associa le tecniche Mitre ATT&CK.
        """
        technique_ids = set()

        # 1. Keyword based matching
        content_lower = content.lower()
        for key, ids in cls.KEYWORD_MAPPINGS.items():
            if key in content_lower:
                technique_ids.update(ids)

        if not technique_ids:
            return 0

        # 2. Associazione nel DB
        # Verifica quali tecniche esistono già
        result = await db.execute(select(MitreTechnique).where(MitreTechnique.id.in_(list(technique_ids))))
        existing_techniques = result.scalars().all()

        for tech in existing_techniques:
            # Associazione idempotente
            check = await db.execute(
                select(mitre_leaks).where(mitre_leaks.c.mitre_id == tech.id, mitre_leaks.c.leak_id == leak_id)
            )
            if not check.first():
                await db.execute(mitre_leaks.insert().values(mitre_id=tech.id, leak_id=leak_id))
                logger.info(f"[MITRE] Leak {leak_id} mapped to {tech.id} ({tech.name})")

        await db.commit()
        return len(existing_techniques)
