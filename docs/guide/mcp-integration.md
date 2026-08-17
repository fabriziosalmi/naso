# Model Context Protocol (MCP) Integration

`backend/mcp_server.py` speaks the Model Context Protocol over stdio, so an
MCP client — Claude Desktop, an IDE extension — can query NASO and run OSINT
probes without going through the HTTP API.

## What it exposes

Six tools, and nothing else:

| Tool | What it does |
|---|---|
| `naso_darkweb_recon` | Ahmia search through the Tor cluster |
| `naso_shodan_scan` | Shodan lookup for one IP |
| `naso_telegram_intel` | Read a public Telegram channel |
| `naso_get_identities` | List monitored identities |
| `naso_get_leaks` | List leak hits |
| `naso_protect_identity` | Toggle VIP protection — the one tool here that writes |

::: warning It connects to the database directly
The server opens its own `AsyncSessionLocal` against `DATABASE_URL`. It is a
second door into the same data, and it does not carry an operator's session —
so it does not apply the per-user tenant scoping the HTTP API applies. Run it
only on a machine you would give database credentials to, and do not expose it
to a client you would not give the same access.
:::

## Setup Instructions (Claude Desktop)

To bind Claude Desktop to your local NASO deployment, you must edit your Claude configuration file.

### Prerequisites
- Python 3.11 with the `mcp` SDK 2.x (`pip install 'mcp>=2.0.0,<3'`). The
  ceiling matters: the server is written against the 2.x `MCPServer` API, and
  the 1.x decorator API it used before did not survive the major bump.
- A running NASO Postgres, reachable at `DATABASE_URL`.
- The id of the tenant this server should be bound to:

```bash
docker exec naso-db psql -U "$DB_USER" -d "$DB_NAME" -c 'select id, name from tenants'
```

### Modifying Configuration
Locate your `claude_desktop_config.json`:
- **macOS**: `~/Library/Application Support/Claude/claude_desktop_config.json`
- **Windows**: `%APPDATA%\Claude\claude_desktop_config.json`

Add the following JSON block:

```json
{
  "mcpServers": {
    "naso_forensic": {
      "command": "python3",
      "args": ["backend/mcp_server.py"],
      "cwd": "/absolute/path/to/your/naso/repo",
      "env": {
        "DATABASE_URL": "postgresql+asyncpg://user:pass@localhost:5432/naso_db",
        "NASO_MCP_TENANT_ID": "the-tenant-uuid-from-above"
      }
    }
  }
}
```

`NASO_MCP_TENANT_ID` is required and the server refuses to start without it. It
is deliberately not a tool argument: an argument is chosen by the model, and a
model that can name one tenant can name another.

### What it can do

Once restarted, you can ask Claude Desktop:

> *"Which monitored identities have the highest risk score, and what leaks are they in?"*

The client picks from six tools:

| Tool | |
|---|---|
| `naso_get_identities` | list this tenant's identities |
| `naso_get_leaks` | list this tenant's leak hits, optionally above a severity |
| `naso_darkweb_recon` | Ahmia search through the Tor cluster |
| `naso_shodan_scan` | Shodan lookup for one IPv4 address |
| `naso_telegram_intel` | recent public messages from a Telegram channel |
| `naso_protect_identity` | set or clear the VIP flag — the only tool that writes |

The three OSINT tools reach outside your network. That is the point of them, and
also the reason to think about who is driving the client: the same
authorisation rules apply as when you run those probes from the UI.
