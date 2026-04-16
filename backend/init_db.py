import asyncio
from app.database import AsyncSessionLocal, engine
from app.models import Tenant, User, Base, MitreTechnique
from app.core.security import get_password_hash
from sqlalchemy.future import select

async def init():
    # Crea le tabelle in modo asincrono
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    async with AsyncSessionLocal() as db:
        # Crea il tenant di sistema se non esiste
        result = await db.execute(select(Tenant).where(Tenant.name == "System"))
        system_tenant = result.scalar_one_or_none()
        if not system_tenant:
            system_tenant = Tenant(name="System", description="System Management Tenant")
            db.add(system_tenant)
            await db.commit()
            await db.refresh(system_tenant)
            print("System tenant created.")

        # Crea l'utente admin se non esiste
        admin_email = "admin@naso.local"
        result = await db.execute(select(User).where(User.email == admin_email))
        admin_user = result.scalar_one_or_none()
        if not admin_user:
            admin_user = User(
                email=admin_email,
                hashed_password=get_password_hash("rigorous_admin_password_2026"),
                full_name="System Administrator",
                role="admin",
                tenant_id=system_tenant.id
            )
            db.add(admin_user)
            await db.commit()
            print(f"Admin user created: {admin_email}")
        else:
            print(f"Admin user already exists: {admin_email}")

        # Seed Mitre Techniques (CC)
        techniques = [
            {"id": "T1566", "name": "Phishing", "tactic": "Initial Access", "description": "L'avversario invia messaggi per indurre gli utenti a fornire credenziali o scaricare malware."},
            {"id": "T1589", "name": "Gather Victim Identity Information", "tactic": "Reconnaissance", "description": "L'avversario raccoglie informazioni sull'identità delle vittime (es. email) per facilitare l'attacco."},
            {"id": "T1110", "name": "Brute Force", "tactic": "Credential Access", "description": "Tentativo sistematico di indovinare le password."},
            {"id": "T1195", "name": "Supply Chain Compromise", "tactic": "Initial Access", "description": "Compromissione di repository o software di terze parti (es. GitHub)."},
            {"id": "T1555", "name": "Credentials from Web Browsers", "tactic": "Credential Access", "description": "Estrazione di password salvate nel browser."},
            {"id": "T1608", "name": "Stage Capabilities", "tactic": "Resource Development", "description": "Preparazione di infrastrutture per l'attacco."}
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
