import asyncio
import contextlib
import logging
from typing import Any

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import TextContent, Tool
from sqlalchemy.future import select

# NASO Imports
from shared.database import AsyncSessionLocal
from shared.domain.services.darkweb_search import DarkWebSearchService
from shared.domain.services.shodan_search import ShodanService
from shared.domain.services.telegram_search import TelegramOSINTService
from shared.models import Identity, LeakHit
from shared.utils.audit import AuditLogger

# Configurazione Logger per non inquinare stdio (che romperrebbe MCP protocol)
logging.basicConfig(level=logging.ERROR)
logger = logging.getLogger("naso-mcp")

app = Server("naso-forensic-mcp")


@app.list_tools()
async def list_tools() -> list[Tool]:
    """Lista dei tool OSINT esposti da NASO MCP."""
    return [
        Tool(
            name="naso_darkweb_recon",
            description="Launch an autonomous OSINT probe into the Dark Web (Onion services) using Ahmia algorithms to search for specific strings, names, hashes or signatures.",
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "The exact string, name, email or hash to look for in encrypted networks.",
                    }
                },
                "required": ["query"],
            },
        ),
        Tool(
            name="naso_shodan_scan",
            description="Query Shodan OSINT to discover open ports, vulnerabilities, and exposed services for a specific IP address.",
            inputSchema={
                "type": "object",
                "properties": {
                    "target_ip": {"type": "string", "description": "The IPv4 address to scan (e.g. '8.8.8.8')."}
                },
                "required": ["target_ip"],
            },
        ),
        Tool(
            name="naso_telegram_intel",
            description="Scrape and intercept the most recent public messages from a Telegram channel. Best used for monitoring threat actor groups or hacktivist leaks.",
            inputSchema={
                "type": "object",
                "properties": {
                    "channel_name": {
                        "type": "string",
                        "description": "The telegram channel alias/name (e.g. 'lockbit_news' or 'hacktivist_group').",
                    }
                },
                "required": ["channel_name"],
            },
        ),
        Tool(
            name="naso_get_identities",
            description="Fetch a list of active master identities monitored by the NASO intelligence engine.",
            inputSchema={
                "type": "object",
                "properties": {
                    "limit": {"type": "integer", "description": "Limiter for total identities fetched.", "default": 50}
                },
            },
        ),
        Tool(
            name="naso_get_leaks",
            description="Acquire the persistent database of intercepted data leaks and threat artifacts. Useful for AI Triage.",
            inputSchema={
                "type": "object",
                "properties": {
                    "min_severity": {
                        "type": "integer",
                        "description": "Minimum threat severity score (0 to 100). E.g., 80 for criticals.",
                        "default": 0,
                    }
                },
            },
        ),
        Tool(
            name="naso_protect_identity",
            description="Actively mark an identity as VIP (Protected) in the database, instructing the engine to elevate its correlation priority.",
            inputSchema={
                "type": "object",
                "properties": {
                    "identity_id": {"type": "string", "description": "The UUID of the identity to protect."},
                    "is_protected": {"type": "boolean", "description": "True to protect, False to unprotect."},
                },
                "required": ["identity_id", "is_protected"],
            },
        ),
    ]


@app.call_tool()
async def call_tool(name: str, arguments: dict[str, Any]) -> list[TextContent]:
    """Gestore unificato delle chiamate Tool."""

    # ── Database Session Wrapper ──
    async def get_db_session():
        db = AsyncSessionLocal()
        try:
            yield db
        finally:
            await db.close()

    if name == "naso_darkweb_recon":
        query = arguments.get("query")
        if not query:
            return [TextContent(type="text", text="Error: Query is required.")]

        try:
            # MCP Bypass: DarkWebSearchService non richiede db nel signature primario, ma esegue call esterne.
            results = await DarkWebSearchService.search_onion_links(query)

            # Formattiamo logica per LLM
            if not results:
                return [TextContent(type="text", text=f"No results found for query: {query}")]

            report = f"Dark Web Report for '{query}':\n\n"
            for res in results:
                report += f"- Title: {res['title']}\n  URL: {res['url']}\n  Snippet: {res['snippet']}\n\n"

            return [TextContent(type="text", text=report)]
        except Exception as e:
            return [TextContent(type="text", text=f"Dark web recon failed: {str(e)}")]

    elif name == "naso_shodan_scan":
        target_ip = arguments.get("target_ip")
        if not target_ip:
            return [TextContent(type="text", text="Error: target_ip is required.")]

        try:
            results = await ShodanService.scan_host(target_ip)
            if "error" in results:
                return [TextContent(type="text", text=f"Shodan Scan Error: {results['error']}")]

            report = f"Shodan Intel for IP: {target_ip}\n"
            report += f"ISP: {results.get('isp')} | Org: {results.get('org')}\n"
            report += f"OS: {results.get('os')} | Open Ports: {results.get('ports')}\n\n"

            for d in results.get("data_summary", []):
                report += f"- Port {d.get('port')}: {d.get('product') or 'Unknown'} {d.get('version') or ''}\n"

            if results.get("vulns"):
                report += f"\nVulnerabilities (CVEs): {', '.join(results.get('vulns'))}\n"

            return [TextContent(type="text", text=report)]
        except Exception as e:
            return [TextContent(type="text", text=f"Shodan scan failed: {str(e)}")]

    elif name == "naso_telegram_intel":
        channel_name = arguments.get("channel_name")
        if not channel_name:
            return [TextContent(type="text", text="Error: channel_name is required.")]

        try:
            results = await TelegramOSINTService.scrape_public_channel(channel_name)
            if not results:
                return [TextContent(type="text", text=f"No messages found for channel @{channel_name}.")]

            if "error" in results[0]:
                return [TextContent(type="text", text=f"Telegram Intel Error: {results[0]['error']}")]

            report = f"Telegram Threat Chatter intercepted from @{channel_name}:\n\n"
            for msg in results:
                report += f"[{msg.get('timestamp')}] (Views: {msg.get('views')})\n{msg.get('text')}\n---\n"

            return [TextContent(type="text", text=report)]
        except Exception as e:
            return [TextContent(type="text", text=f"Telegram intel failed: {str(e)}")]

    elif name == "naso_get_identities":
        limit = arguments.get("limit", 50)
        async for db in get_db_session():
            try:
                stmt = select(Identity).limit(limit)
                result = await db.execute(stmt)
                identities = result.scalars().all()
                out = "Monitored Identities:\n"
                for i in identities:
                    out += f"ID: {i.id} | Identifier: {i.identifier} | Type: {i.type} | Risk: {i.risk_score} | Protected: {i.is_protected}\n"
                return [TextContent(type="text", text=out or "No identities tracked yet.")]
            except Exception as e:
                return [TextContent(type="text", text=f"Database error: {str(e)}")]

    elif name == "naso_get_leaks":
        min_sev = arguments.get("min_severity", 0)
        async for db in get_db_session():
            try:
                stmt = (
                    select(LeakHit)
                    .where(LeakHit.severity_score >= min_sev)
                    .order_by(LeakHit.discovered_at.desc())
                    .limit(100)
                )
                result = await db.execute(stmt)
                leaks = result.scalars().all()
                out = f"Recorded Leaked Artifacts (Severity >= {min_sev}):\n"
                for leak in leaks:
                    out += (
                        f"ID: {leak.id} | Source: {leak.source} | Severity: {leak.severity_score} "
                        f"| DB_Status: {leak.status}\nSnippet: {leak.content_snippet}\n\n"
                    )
                return [TextContent(type="text", text=out or "No intelligence artifacts match criteria.")]
            except Exception as e:
                return [TextContent(type="text", text=f"Database error: {str(e)}")]

    elif name == "naso_protect_identity":
        identity_id = arguments.get("identity_id")
        is_protected = arguments.get("is_protected")
        if not identity_id:
            return [TextContent(type="text", text="Error: identity_id is required.")]

        async for db in get_db_session():
            try:
                stmt = select(Identity).where(Identity.id == identity_id)
                result = await db.execute(stmt)
                identity = result.scalar_one_or_none()
                if not identity:
                    return [TextContent(type="text", text=f"Identity {identity_id} not found.")]

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
                return [
                    TextContent(
                        type="text", text=f"Identity {identity.identifier} protection status set to: {is_protected}."
                    )
                ]
            except Exception as e:
                return [TextContent(type="text", text=f"Database error: {str(e)}")]

    return [TextContent(type="text", text=f"Unknown tool: {name}")]


async def main():
    """Lancia l'engine MCP su server STDIO."""
    async with stdio_server() as (read_stream, write_stream):
        await app.run(read_stream, write_stream, app.create_initialization_options())


if __name__ == "__main__":
    asyncio.run(main())
