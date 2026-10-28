# FastMCP 201: from a server that works to a server you can govern

The hands-on for the MCP 201 session (GSA MCP Hackathon, 2026-10-28). One
server, four acts, one command per act.

- `server.py`: the 101 weather server at the top, unchanged, then four acts
  that each add one layer to it, narrated in the comments. This is the file on
  screen.
- `demo.py`: `uv run python demo.py 1` through `4` plays that act against a
  live copy of `server.py` with labeled output, then shuts it down. `demo.py
  proxy` and `demo.py skill` are the optional extras.
- `lab.py`: the plumbing behind `demo.py` (subprocess server, token minting, client calls).
- `weather/keys.py`: the demo identity provider's key pair, generated into `keys/` on first use.
- `tests/`: in-memory tests for every act plus one subprocess smoke test per demo (`uv run pytest`).
- `setup_client.py`, `PROMPTS.md`: the Claude Code side of the live show, one
  `.mcp.json` entry and the talk track per act.
- `skills_server.py`, `skills/rain-outlook/`: the server plus one skill, FastMCP 4.2.0a1 only.
- `RUN.md`: the four commands with expected output, and the live Claude Code setup.

| Act | Adds | Minutes |
|---|---|---|
| I · Who's calling | `JWTVerifier`, a locally minted token, `require_scopes` on one tool | 12 |
| II · The path, not the prompt | `LoggingMiddleware` plus a dozen-line redaction middleware; optional `ProxyProvider` | 13 |
| III · Tasks and questions | `TasksExtension` on `memory://`, a `task=True` tool with `Progress`, an elicitation | 14 |
| IV · The agent's head | `BM25SearchTransform` and `CodeMode` on two in-process views of the server; optional `Skill` | 12 |

Versions: `fastmcp[tasks,code-mode]==4.1.4` (`.venv`); `fastmcp==4.2.0a1`
(`.venv-skills`) only for the optional skill. Port 8201.
