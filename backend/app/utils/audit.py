from sqlalchemy.ext.asyncio import AsyncSession
from ..models import AuditLog
import json

class AuditLogger:
    """
    Utility per il tracciamento delle azioni degli analisti (#10).
    """
    @staticmethod
    async def log(
        db: AsyncSession, 
        user_id: str, 
        tenant_id: str, 
        action: str, 
        resource_type: str = None, 
        resource_id: str = None, 
        details: dict = None,
        ip_address: str = None
    ):
        log_entry = AuditLog(
            user_id=user_id,
            tenant_id=tenant_id,
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            details=details,
            ip_address=ip_address
        )
        db.add(log_entry)
        await db.flush() # Persisti senza commit totale se in transazione
