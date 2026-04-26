import asyncio
import random
import uuid
from datetime import UTC, datetime, timedelta

from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn

from shared.database import async_session
from shared.models import Identity, LeakHit, Tenant

console = Console()

# Configure Synthetic Operation Target
OPERATION_NAME = "Operation Lazarus Drop"
TARGET_DOMAIN = "corp.local"

VIP_IDENTITIES = [f"ceo@{TARGET_DOMAIN}", f"cto@{TARGET_DOMAIN}", f"admin-root@{TARGET_DOMAIN}"]

STANDARD_IDENTITIES = (
    [f"dev_team_{i}@{TARGET_DOMAIN}" for i in range(1, 15)]
    + [f"hr_{i}@{TARGET_DOMAIN}" for i in range(1, 6)]
    + [f"contractor_{i}@vendor.local" for i in range(1, 10)]
)

LEAK_SOURCES = ["github", "darkweb", "telegram", "pastebin", "shodan"]
YARA_HITS = ["SUSP_OBFUSCATED_POWERSHELL", "CREDENTIAL_DUMP_LSASS", "RANSOMWARE_RYUK_TRACE", "APT29_BEACON_PAYLOAD"]


async def seed_demo():
    console.print("\n[bold cyan]🚀 NASO Forensic Engine - Bootstrapping Zero-to-Hero Demo Data...[/bold cyan]\n")

    async with async_session() as db:
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            transient=True,
        ) as progress:
            task1 = progress.add_task("[yellow]Initializing Core Tenant (Demo Corp Intel)...", total=1)

            # Check for demo tenant or fallback to default
            tenant = Tenant(name="Demo Corp Intel")
            db.add(tenant)
            await db.commit()
            await db.refresh(tenant)
            progress.update(task1, advance=1, description="[green]Tenant initialized.")

            tenant_id = tenant.id
            identity_objects = []

            task2 = progress.add_task(
                "[yellow]Seeding High-Profile Identities (VIP & Standard)...",
                total=len(VIP_IDENTITIES) + len(STANDARD_IDENTITIES),
            )

            # 1. Seed VIPs
            for identifier in VIP_IDENTITIES:
                i = Identity(
                    identifier=identifier,
                    type="email",
                    tenant_id=tenant_id,
                    risk_score=random.randint(85, 100),
                    is_protected=True,
                )
                db.add(i)
                identity_objects.append(i)
                progress.update(task2, advance=1)

            # 2. Seed Standard Employees
            for identifier in STANDARD_IDENTITIES:
                i = Identity(
                    identifier=identifier,
                    type="email",
                    tenant_id=tenant_id,
                    risk_score=random.randint(10, 60),
                    is_protected=False,
                )
                db.add(i)
                identity_objects.append(i)
                progress.update(task2, advance=1)

            await db.commit()
            progress.update(task2, description=f"[green]Generated {len(identity_objects)} identities.")

            task3 = progress.add_task(f"[red]Deploying {OPERATION_NAME} Vectors...", total=len(identity_objects))
            leak_count = 0
            now = datetime.now(UTC)

            for ident in identity_objects:
                num_leaks = random.randint(5, 15) if ident.is_protected else random.randint(1, 5)

                for _ in range(num_leaks):
                    severity = random.randint(80, 100) if ident.is_protected else random.randint(20, 80)
                    source = random.choice(LEAK_SOURCES)
                    yara_rule = random.choice(YARA_HITS)
                    date_offset = timedelta(days=random.randint(0, 30), hours=random.randint(0, 24))

                    ai_meta = {
                        "ai_thought": f"Analyzed raw dump from {source}. Pattern matches YARA {yara_rule}. Validating credential leak likelihood -> Critical.",
                        "ai_analysis": f"Confidence: 99%. Target {ident.identifier} exposed in multi-vector breach. Recommend instant LDAP rotation.",
                    }

                    leak = LeakHit(
                        tenant_id=tenant_id,
                        source=source,
                        severity_score=severity,
                        content_snippet=f"[ENCRYPTED] APT payload traced from {source}. Rule: {yara_rule} triggered. Target: {ident.identifier} ID: {uuid.uuid4().hex[:8]}",
                        discovered_at=now - date_offset,
                        status="new" if severity > 50 else "reviewing",
                        metadata_json=ai_meta,
                    )

                    leak.identities.append(ident)
                    db.add(leak)
                    leak_count += 1

                progress.update(task3, advance=1)

            await db.commit()
            progress.update(
                task3, description=f"[green]Seeded {leak_count} individual node connections to the Topology Matrix."
            )

    console.print(
        f"\n[bold green]🎉 Operation Lazarus successfully injected {leak_count} massive leak artifacts![/bold green]"
    )
    console.print("[dim italic]Refresh the NASO frontend Topology Matrix to analyze the blast radius.[/dim italic]\n")


if __name__ == "__main__":
    asyncio.run(seed_demo())
