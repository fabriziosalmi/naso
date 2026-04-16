import asyncio
import logging
from typing import Any, List, Optional
from mcp.server import Server
from mcp.types import Tool, TextContent
from mcp.server.stdio import stdio_server
from sqlalchemy.future import select

# NASO Imports
from shared.database import AsyncSessionLocal
from shared.models import Identity, LeakHit
from shared.domain.services.darkweb_search import DarkWebSearchService
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
                        "description": "The exact string, name, email or hash to look for in encrypted networks."
                    }
                },
                "required": ["query"]
            }
        ),
        Tool(
            name="naso_get_identities",
            description="Fetch a list of active master identities monitored by the NASO intelligence engine.",
            inputSchema={
                "type": "object",
                "properties": {
                    "limit": {
                        "type": "integer",
                        "description": "Limiter for total identities fetched.",
                        "default": 50
                    }
                }
            }
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
                        "default": 0
                    }
                }
            }
        ),
        Tool(
            name="naso_protect_identity",
            description="Actively mark an identity as VIP (Protected) in the database, instructing the engine to elevate its correlation priority.",
            inputSchema={
                "type": "object",
                "properties": {
                    "identity_id": {
                        "type": "string",
                        "description": "The UUID of the identity to protect."
                    },
                    "is_protected": {
                        "type": "boolean",
                        "description": "True to protect, False to unprotect."
                    }
                },
                "required": ["identity_id", "is_protected"]
            }
        )
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
                stmt = select(LeakHit).where(LeakHit.severity_score >= min_sev).order_by(LeakHit.discovered_at.desc()).limit(100)
                result = await db.execute(stmt)
                leaks = result.scalars().all()
                out = f"Recorded Leaked Artifacts (Severity >= {min_sev}):\n"
                for l in leaks:
                    out += f"ID: {l.id} | Source: {l.source} | Severity: {l.severity_score} | DB_Status: {l.status}\nSnippet: {l.content_snippet}\n\n"
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
                try:
                    await AuditLogger.log(
                        db,
                        user_id="MCP_AGENT",
                        tenant_id=identity.tenant_id,
                        action="MCP_TOOL_UPDATE_PROTECTION",
                        resource_type="identity",
                        resource_id=identity_id,
                        details={"is_protected": is_protected}
                    )
                except Exception:
                    pass
                    
                await db.commit()
                return [TextContent(type="text", text=f"Identity {identity.identifier} protection status set to: {is_protected}.")]
            except Exception as e:
                return [TextContent(type="text", text=f"Database error: {str(e)}")]

    return [TextContent(type="text", text=f"Unknown tool: {name}")]


async def main():
    """Lancia l'engine MCP su server STDIO."""
    async with stdio_server() as (read_stream, write_stream):
        await app.run(
            read_stream,
            write_stream,
            app.create_initialization_options()
        )

if __name__ == "__main__":
    asyncio.run(main())
