# Model Context Protocol (MCP) Integration

NASO provides a native standard-compliant MCP (Model Context Protocol) Server. This allows GenAI assistants like **Claude Desktop** or specialized IDE extensions to directly communicate, query, and perform OSINT tasks without requiring an intermediate API middleware setup.

## What is MCP?
The Model Context Protocol establishes an open standard enabling AI assistants to uniformly access external capabilities. By implementing an MCP server (`backend/mcp_server.py`), NASO exposes its entire forensic database, Identity Correlation mapping, and dark-web probe capabilities to external neural engines.

## Setup Instructions (Claude Desktop)

To bind Claude Desktop to your local NASO deployment, you must edit your Claude configuration file.

### Prerequisites
- Python 3.9+ with `mcp` SDK installed (`pip install mcp>=1.2.0`).
- NASO PostgreSQL instance running locally.

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
      "args": ["-m", "backend.mcp_server"],
      "cwd": "/absolute/path/to/your/naso/repo"
    }
  }
}
```

### Agentic Capabilities
Once restarted, you can ask Claude Desktop:
> *"Query the NASO graph for any identities linked to the email target@company.com and cross-reference them with the latest leaks."*

Claude will automatically execute the exposed tools (`search_identities`, `run_darkweb_probe`, or `search_leaks`), read the streaming stdout responses, and formulate tactical insights seamlessly.
