"""NASO MCP server — six OSINT tools over stdio.

Ported to the current SDK. The previous implementation was written against the
`@app.list_tools()` / `@app.call_tool()` decorators of an early `mcp` release,
and `requirements.txt` pins `mcp>=1.28.1` with no ceiling. Against the 2.0.0 the
project actually installs, the module did not import at all:

    AttributeError: 'Server' object has no attribute 'list_tools'

which means this feature — advertised on the documentation home page, with a
guide page of its own — had been dead for as long as the pin allowed the SDK to
move. Nothing imported it, so nothing failed, and no test covered it.

The other change is tenant scoping; see :func:`mcp_tenant_id`.
"""

import contextlib
import logging
import os
import uuid

from mcp.server.mcpserver import MCPServer
from sqlalchemy.future import select

from shared.database import AsyncSessionLocal
from shared.domain.services.darkweb_search import DarkWebSearchService
from shared.domain.services.shodan_search import ShodanService
from shared.domain.services.telegram_search import TelegramOSINTService
from shared.models import Identity, LeakHit
from shared.utils.audit import AuditLogger

# Configure the logger so it never writes to stdio, which would break the MCP protocol
logging.basicConfig(level=logging.ERROR)
logger = logging.getLogger("naso-mcp")

server = MCPServer(
    name="naso-forensic-mcp",
    instructions=(
        "Read and act on one NASO tenant's exposure data. Every tool is scoped "
        "to the tenant this server was started for; there is no way to ask it "
        "about another one."
    ),
)


def mcp_tenant_id() -> str:
    """The single tenant this server instance is allowed to see.

    Every query here used to be unscoped — `select(Identity).limit(...)` and
    `select(LeakHit).where(severity >= ...)`, with no tenant filter anywhere in
    the file. On a multi-tenant deployment that handed whoever drove the MCP
    client every tenant's identities and every tenant's leak snippets, while the
    HTTP API next door filters each of those queries on the caller's tenant.

    Binding the server to one tenant through the environment rather than through
    a tool argument is deliberate: a tool argument is model-controlled, and a
    model that can name a tenant can name a different one. This cannot be
    reached from the conversation.
    """
    tenant_id = os.environ.get("NASO_MCP_TENANT_ID", "").strip()
    if not tenant_id:
        raise RuntimeError(
            "NASO_MCP_TENANT_ID is not set. This server reads the database "
            "directly and carries no operator session, so it has to be bound to "
            "one tenant explicitly — otherwise every query returns every "
            "tenant's data. Set it in the MCP client's env block."
        )
    # Shape-checked, because the failure mode of a typo is silence: every tool
    # returns "no results", which reads as an empty tenant rather than as a
    # misconfiguration, and an operator can spend a long time looking at the
    # wrong thing. Tenant ids are UUIDs (`shared/models.py`).
    try:
        uuid.UUID(tenant_id)
    except ValueError as exc:
        raise RuntimeError(
            f"NASO_MCP_TENANT_ID is not a UUID: {tenant_id!r}. Tenant ids look "
            "like 3f2504e0-4f89-11d3-9a0c-0305e82c3301 — list them with "
            "`docker exec naso-db psql -U $DB_USER -d $DB_NAME -c 'select id, name from tenants'`."
        ) from exc
    return tenant_id


async def get_db_session():
    """One session per tool call, closed on the way out."""
    db = AsyncSessionLocal()
    try:
        yield db
    finally:
        await db.close()


@server.tool(
    description=(
        "Launch an OSINT probe into onion services through the Tor cluster, using Ahmia, "
        "for a specific string, name, hash or signature."
    )
)
async def naso_darkweb_recon(query: str) -> str:
    """Search onion services for *query*."""
    if not query:
        return "Error: Query is required."
    try:
        results = await DarkWebSearchService.search_onion_links(query)
        if not results:
            return f"No results found for query: {query}"

        report = f"Dark Web Report for '{query}':\n\n"
        for res in results:
            report += f"- Title: {res['title']}\n  URL: {res['url']}\n  Snippet: {res['snippet']}\n\n"
        return report
    except Exception as e:
        return f"Dark web recon failed: {str(e)}"


@server.tool(description="Query Shodan for open ports, exposed services and known CVEs on a single IPv4 address.")
async def naso_shodan_scan(target_ip: str) -> str:
    """Shodan lookup for *target_ip*."""
    if not target_ip:
        return "Error: target_ip is required."
    try:
        results = await ShodanService.scan_host(target_ip)
        if "error" in results:
            return f"Shodan Scan Error: {results['error']}"

        report = f"Shodan Intel for IP: {target_ip}\n"
        report += f"ISP: {results.get('isp')} | Org: {results.get('org')}\n"
        report += f"OS: {results.get('os')} | Open Ports: {results.get('ports')}\n\n"
        for d in results.get("data_summary", []):
            report += f"- Port {d.get('port')}: {d.get('product') or 'Unknown'} {d.get('version') or ''}\n"
        if results.get("vulns"):
            report += f"\nVulnerabilities (CVEs): {', '.join(results.get('vulns'))}\n"
        return report
    except Exception as e:
        return f"Shodan scan failed: {str(e)}"


@server.tool(
    description=(
        "Read the most recent public messages from a Telegram channel — for monitoring "
        "threat actor groups and leak channels."
    )
)
async def naso_telegram_intel(channel_name: str) -> str:
    """Read the public messages of *channel_name*."""
    if not channel_name:
        return "Error: channel_name is required."
    try:
        results = await TelegramOSINTService.scrape_public_channel(channel_name)
        if not results:
            return f"No messages found for channel @{channel_name}."
        if "error" in results[0]:
            return f"Telegram Intel Error: {results[0]['error']}"

        report = f"Telegram Threat Chatter intercepted from @{channel_name}:\n\n"
        for msg in results:
            report += f"[{msg.get('timestamp')}] (Views: {msg.get('views')})\n{msg.get('text')}\n---\n"
        return report
    except Exception as e:
        return f"Telegram intel failed: {str(e)}"


@server.tool(description="List the identities this tenant monitors, highest risk first.")
async def naso_get_identities(limit: int = 50) -> str:
    """List monitored identities, highest risk first, capped at *limit*.

    The ordering is explicit and the limit is clamped: without an ORDER BY the
    result order is whatever the database felt like, and `limit` arrives from a
    model, which can ask for a million rows as easily as fifty.
    """
    limit = max(1, min(int(limit), 200))
    async for db in get_db_session():
        try:
            stmt = (
                select(Identity)
                .where(Identity.tenant_id == mcp_tenant_id())
                .order_by(Identity.risk_score.desc(), Identity.id)
                .limit(limit)
            )
            identities = (await db.execute(stmt)).scalars().all()
            if not identities:
                return "No identities tracked yet."
            out = "Monitored Identities:\n"
            for i in identities:
                out += (
                    f"ID: {i.id} | Identifier: {i.identifier} | Type: {i.type} "
                    f"| Risk: {i.risk_score} | Protected: {i.is_protected}\n"
                )
            return out
        except Exception as e:
            return f"Database error: {str(e)}"


@server.tool(description="List this tenant's recorded leak hits, optionally above a severity threshold.")
async def naso_get_leaks(min_severity: int = 0) -> str:
    """List leak hits scoring at least *min_severity*."""
    async for db in get_db_session():
        try:
            stmt = (
                select(LeakHit)
                .where(
                    LeakHit.tenant_id == mcp_tenant_id(),
                    LeakHit.severity_score >= min_severity,
                )
                .order_by(LeakHit.discovered_at.desc())
                .limit(100)
            )
            leaks = (await db.execute(stmt)).scalars().all()
            if not leaks:
                return "No intelligence artifacts match criteria."
            out = f"Recorded Leaked Artifacts (Severity >= {min_severity}):\n"
            for leak in leaks:
                out += (
                    f"ID: {leak.id} | Source: {leak.source} | Severity: {leak.severity_score} "
                    f"| DB_Status: {leak.status}\nSnippet: {leak.content_snippet}\n\n"
                )
            return out
        except Exception as e:
            return f"Database error: {str(e)}"


@server.tool(description="Mark one identity as protected (VIP), or clear that flag.")
async def naso_protect_identity(identity_id: str, is_protected: bool) -> str:
    """Set the protection flag on *identity_id*."""
    async for db in get_db_session():
        try:
            # Scoped like the read tools, and for a stronger reason: this one
            # writes. An id names a row; it does not authorise touching it.
            # Answering "not found" for another tenant's identity matches what
            # the HTTP API does with the same situation.
            stmt = select(Identity).where(
                Identity.id == identity_id,
                Identity.tenant_id == mcp_tenant_id(),
            )
            identity = (await db.execute(stmt)).scalar_one_or_none()
            if not identity:
                return f"Identity {identity_id} not found."

            identity.is_protected = is_protected

            # Traccia MCP a livello di Audit NASO
            with contextlib.suppress(Exception):
                await AuditLogger.log(
                    db,
                    user_id="MCP_AGENT",
                    tenant_id=identity.tenant_id,
                    action="MCP_TOOL_UPDATE_PROTECTION",
                    resource_type="identity",
                    resource_id=identity_id,
                    details={"is_protected": is_protected},
                )

            await db.commit()
            return f"Identity {identity.identifier} protection status set to: {is_protected}."
        except Exception as e:
            return f"Database error: {str(e)}"


async def main():
    """Run the MCP engine over stdio."""
    # Fail at startup, not on the first query: a client that connects and then
    # gets an error from every tool looks like a broken deployment, while a
    # server that refuses to start says exactly what is missing.
    mcp_tenant_id()
    await server.run_stdio_async()


if __name__ == "__main__":
    import asyncio

    asyncio.run(main())
