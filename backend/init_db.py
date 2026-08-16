import asyncio
import os

from sqlalchemy.future import select

from shared.core.security import get_password_hash
from shared.database import AsyncSessionLocal, engine
from shared.models import Base, MitreTechnique, Tenant, User


async def init():
    # Create the tables asynchronously
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with AsyncSessionLocal() as db:
        # Create the system tenant if it does not exist
        result = await db.execute(select(Tenant).where(Tenant.name == "System"))
        system_tenant = result.scalar_one_or_none()
        if not system_tenant:
            system_tenant = Tenant(name="System", description="System Management Tenant")
            db.add(system_tenant)
            await db.commit()
            await db.refresh(system_tenant)
            print("System tenant created.")

        # Create the admin user if it does not exist
        # SECURITY: set NASO_ADMIN_EMAIL and NASO_ADMIN_PASSWORD env vars in production
        admin_email = os.environ.get("NASO_ADMIN_EMAIL", "admin@naso.local")
        admin_password = os.environ.get("NASO_ADMIN_PASSWORD")
        result = await db.execute(select(User).where(User.email == admin_email))
        admin_user = result.scalar_one_or_none()
        if not admin_user:
            if not admin_password:
                raise RuntimeError(
                    "NASO_ADMIN_PASSWORD env var is not set. Set it to provision the initial admin user."
                )
            admin_user = User(
                email=admin_email,
                hashed_password=get_password_hash(admin_password),
                full_name="System Administrator",
                role="admin",
                tenant_id=system_tenant.id,
            )
            db.add(admin_user)
            await db.commit()
            print(f"Admin user created: {admin_email}")
        else:
            print(f"Admin user already exists: {admin_email}")

        # Seed Mitre Techniques (CC)
        techniques = [
            {
                "id": "T1566",
                "name": "Phishing",
                "tactic": "Initial Access",
                "description": "The adversary sends messages to trick users into handing over credentials or downloading malware.",
            },
            {
                "id": "T1589",
                "name": "Gather Victim Identity Information",
                "tactic": "Reconnaissance",
                "description": "The adversary gathers identity information about the victims (e.g. email addresses) to enable the attack.",
            },
            {
                "id": "T1110",
                "name": "Brute Force",
                "tactic": "Credential Access",
                "description": "Systematic attempts to guess passwords.",
            },
            {
                "id": "T1195",
                "name": "Supply Chain Compromise",
                "tactic": "Initial Access",
                "description": "Compromissione di repository o software di terze parti (es. GitHub).",
            },
            {
                "id": "T1555",
                "name": "Credentials from Web Browsers",
                "tactic": "Credential Access",
                "description": "Extraction of passwords stored in the browser.",
            },
            {
                "id": "T1608",
                "name": "Stage Capabilities",
                "tactic": "Resource Development",
                "description": "The adversary prepares infrastructure for the attack.",
            },
        ]

        for tech_data in techniques:
            result = await db.execute(select(MitreTechnique).where(MitreTechnique.id == tech_data["id"]))
            tech_check = result.scalar_one_or_none()
            if not tech_check:
                db.add(MitreTechnique(**tech_data))

        await db.commit()
        print(f"Mitre techniques seeded: {len(techniques)}")


if __name__ == "__main__":
    asyncio.run(init())
