"""Write .mcp.json for the live demo: one entry, `weather`, pointing at the server on port 8201.

    uv run python setup_client.py

Mints a token with both scopes (weather:read, weather:write) using the demo
keys in keys/ (local only) and writes it in literally, so there is nothing to
export. Rerun when it expires (24 hours). Claude Code asks once, in /mcp, to
approve the project server; that is the only click.

Everything in the session runs against this one entry. Acts I to III are the
server as started; for Act IV you restart the same process with --view search
or --view code (same port), and for the optional skill you start
skills_server.py instead (same port). The entry never changes.
"""

import json
from pathlib import Path

from lab import PORT, mint

ROOT = Path(__file__).resolve().parent
TTL = 24 * 3600


def build(token: str) -> dict:
    return {"weather": {"type": "http", "url": f"http://127.0.0.1:{PORT}/mcp", "headers": {"Authorization": f"Bearer {token}"}}}


def main() -> None:
    servers = build(mint("weather:read", "weather:write", ttl=TTL))
    (ROOT / ".mcp.json").write_text(json.dumps({"mcpServers": servers}, indent=2) + "\n")
    print(f"wrote {ROOT / '.mcp.json'}: one server, `weather`, token good for 24 h")


if __name__ == "__main__":
    main()
