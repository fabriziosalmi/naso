import asyncio
import uuid
import random
from datetime import datetime, timedelta
from shared.database import async_session
from shared.models import Tenant, Identity, LeakHit

# Configure Synthetic Operation Target
OPERATION_NAME = "Operation Lazarus Drop"
TARGET_DOMAIN = "corp.local"

VIP_IDENTITIES = [
    f"ceo@{TARGET_DOMAIN}",
    f"cto@{TARGET_DOMAIN}",
    f"admin-root@{TARGET_DOMAIN}"
]

STANDARD_IDENTITIES = [
    f"dev_team_{i}@{TARGET_DOMAIN}" for i in range(1, 15)
] + [
    f"hr_{i}@{TARGET_DOMAIN}" for i in range(1, 6)
] + [
    f"contractor_{i}@vendor.local" for i in range(1, 10)
]

LEAK_SOURCES = ["github", "darkweb", "telegram", "pastebin"]

async def seed_demo():
    print("🚀 NASO Forensic Engine - Bootstrapping Zero-to-Hero Demo Data...")
    
    async with async_session() as db:
        # Check for demo tenant or fallback to default
        tenant = Tenant(name="Demo Corp Intel")
        db.add(tenant)
        await db.commit()
        await db.refresh(tenant)

        tenant_id = tenant.id
        identity_objects = []

        print("🧬 Seeding Master Identities...")
        # 1. Seed VIPs
        for identifier in VIP_IDENTITIES:
            i = Identity(
                identifier=identifier,
                type="email",
                tenant_id=tenant_id,
                risk_score=random.randint(85, 100),
                is_protected=True
            )
            db.add(i)
            identity_objects.append(i)

        # 2. Seed Standard Employees
        for identifier in STANDARD_IDENTITIES:
            i = Identity(
                identifier=identifier,
                type="email",
                tenant_id=tenant_id,
                risk_score=random.randint(10, 60),
                is_protected=False
            )
            db.add(i)
            identity_objects.append(i)
        
        await db.commit()
        print(f"✅ Generated {len(identity_objects)} identities.")

        print("🔥 Generating Operation Lazarus Leak Vectors...")
        leak_count = 0
        now = datetime.utcnow()

        for ident in identity_objects:
            # VIPs get highly critical structural leaks
            if ident.is_protected:
                num_leaks = random.randint(5, 15)
            else:
                num_leaks = random.randint(1, 5)

            for _ in range(num_leaks):
                severity = random.randint(80, 100) if ident.is_protected else random.randint(20, 80)
                source = random.choice(LEAK_SOURCES)
                date_offset = timedelta(days=random.randint(0, 30), hours=random.randint(0, 24))
                
                leak = LeakHit(
                    tenant_id=tenant_id,
                    source=source,
                    severity_score=severity,
                    content_snippet=f"[ENCRYPTED] Recovered payload from {source}. Keyword match triggered. ID: {uuid.uuid4().hex[:8]}",
                    discovered_at=now - date_offset,
                    status="new" if severity > 50 else "reviewing"
                )
                
                # Tie leak to the identity
                leak.identities.append(ident)
                db.add(leak)
                leak_count += 1
        
        await db.commit()
        print(f"✅ Seeded {leak_count} individual node connections to the Topology Matrix.")
        print("🎉 Demo Seeding Complete! Refresh the frontend to see the magic.")

if __name__ == "__main__":
    asyncio.run(seed_demo())
