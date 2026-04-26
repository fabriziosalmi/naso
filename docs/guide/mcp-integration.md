# MCP Integration

NASO ships an [MCP](https://modelcontextprotocol.io/) server so a desktop assistant (Claude Desktop, the MCP CLI, any MCP-aware client) can drive an investigation against the analyst's database without going through the SPA.

## Why this exists

The web Co-Analyst ([ai-coanalyst.md](ai-coanalyst.md)) is interactive — a human is sitting at the dashboard, clicking through results. The MCP integration is for the other direction: an analyst asking a desktop LLM "summarise this week's intelligence" and letting the model fetch the data on its own. Same tool semantics; different transport.

## What it exposes

[`backend/mcp_server.py`](https://github.com/fabriziosalmi/naso/blob/main/backend/mcp_server.py). Tools roughly mirror the web Co-Analyst's catalog:

| Tool                          | Purpose                                                       |
|-------------------------------|---------------------------------------------------------------|
| `naso_list_recent_leaks`      | Recent leaks above a severity threshold                       |
| `naso_get_identity_insights`  | Profile + breach history for one identity                     |
| `naso_protect_identity`       | Set / clear VIP protection                                    |
| `naso_search_dark_web`        | Live Ahmia search via the Tor cluster                         |
| `naso_verify_audit_chain`     | Walk the chain, return ok / broken_at / reason                |

(See the source for the up-to-date list — the catalog grows over time.)

Every mutating tool writes the same audit row a normal API call would.

## Configuring Claude Desktop

In `~/Library/Application Support/Claude/claude_desktop_config.json` (macOS) — Linux/Windows paths in [Anthropic's docs](https://modelcontextprotocol.io/quickstart):

```json
{
  "mcpServers": {
    "naso": {
      "command": "docker",
      "args": [
        "exec", "-i", "naso-api",
        "python", "/app/mcp_server.py"
      ]
    }
  }
}
```

Restart Claude Desktop; the NASO tools appear under the 🔌 menu of the chat input.

For a non-Docker deployment, replace `command` + `args` with a path to the Python interpreter and the script. The MCP server reads the same `Settings` as the API, so it needs the same environment (DATABASE_URL, JWT keys, REDIS_HOST, …):

```json
{
  "mcpServers": {
    "naso": {
      "command": "python3",
      "args": ["-m", "backend.mcp_server"],
      "cwd": "/absolute/path/to/your/naso/repo",
      "env": {
        "DATABASE_URL": "postgresql+asyncpg://…",
        "ALGORITHM": "EdDSA",
        "JWT_PUBLIC_KEY": "…",
        "REDIS_HOST": "redis://localhost:6379/0"
      }
    }
  }
}
```

In a Docker deploy, `docker exec` inherits the container env automatically — no `env` block needed.

## Auth model

The MCP server runs **inside the trust boundary** of the API container (or alongside it with the same env). It doesn't perform user-level auth — anyone who can run `docker exec` on the host can use it. That's fine on a single-operator workstation; less fine on a shared bastion.

Hardening options:

- Run the MCP server as a separate container with `cap_drop: ALL` and a specific tenant scope baked into the env.
- Front it with a stdio-bridge that gates by SSH key.
- For multi-operator setups, add a `NASO_MCP_OPERATOR` env var that the server pins all writes to and run one MCP server per operator.

## Example prompts

```
"Summarise everything that came in today for tenant Acme. Cite the
leak IDs of anything I haven't reviewed yet, grouped by source."

"Show me the merge cluster around the riskiest identity in tenant
Acme, then verify the audit chain for that tenant."

"Run a dark-web probe for 'acme breach 2026', then for each result
check whether we already have a near-duplicate in the database."
```

## When to use which

| Situation                                                            | Use                                       |
|----------------------------------------------------------------------|-------------------------------------------|
| Open dashboard, drill into one identity                              | SPA + web Co-Analyst                      |
| Read an alert email, want a quick summary while away from the dashboard | Claude Desktop + MCP                      |
| Build automation around the engine                                   | Direct REST API ([Reference](../api/index.md)) |

The MCP path is convenient but it's not a substitute for the API. Production scripts should hit the REST endpoints directly.
