"""Play one act of server.py against a live server, with labeled output.

    uv run python demo.py 1        Act I    who's calling
    uv run python demo.py 2        Act II   the path, not the prompt
    uv run python demo.py 3        Act III  tools that take time, and tools that ask
    uv run python demo.py 4        Act IV   keep the agent's head clear

Optional:
    uv run python demo.py proxy                     wrap a server you don't own (Act II)
    .venv-skills/bin/python demo.py skill           the methodology as a skill, via skills_server.py (FastMCP 4.2.0a1)

Each command starts server.py on port 8201, mints the tokens it needs, runs
the sequence below, prints each step with a label, and shuts the server down.
"""

import os
import sys

from lab import PORT, ROOT, SKILLS_PORT, Server, checkpoint, mint, quiet_client_logs, say

# The script Act IV runs in code mode: three tool calls, one answer back.
CODE_MODE_SCRIPT = '''
forecast = await call_tool("get_weather_forecast", {"location": "Denver", "days_ahead": 1})
history = await call_tool("get_historical_weather", {"location": "Denver", "date": "2025-11-01"})
rain = await call_tool("calculate_rain_probability", {"location": "Denver", "date": "2026-11-05"})
return {
    "forecast": forecast["result"].splitlines()[2],
    "last_year": history["result"].splitlines()[1],
    "outlook": rain["result"].splitlines()[-2],
}
'''


def act1() -> None:
    read_only = mint("weather:read")
    read_write = mint("weather:read", "weather:write")
    with Server() as s:
        say("No token: the door is shut before any tool runs", s.http_status())
        before = s.list_tools(read_only)
        say("Read-only token: the catalog (the 101 three, plus Act III's two)", "\n".join(before))
        say("Read-only token calls the write tool anyway", s.call("save_favorite_location", {"location": "Denver"}, read_only))
        after = s.list_tools(read_write)
        say("Token with weather:write: one more tool appears", "\n".join(after) + f"\n\nnew: {sorted(set(after) - set(before))}")
        say("Call it", s.call("save_favorite_location", {"location": "Denver"}, read_write))
    checkpoint("the tool list changed and you didn't touch the tool.")


def act2() -> None:
    token = mint("weather:read", "weather:write")
    with Server() as s:
        say("Same call as Act I, through the middleware", s.call("save_favorite_location", {"location": "Denver"}, token))
        say("The server's audit log for that call, one line in, one line out", "\n".join(s.audit_lines("method=tools/call")))
        s.list_tools(token)
        say("Every method gets the same shape (tools/list)", "\n".join(s.audit_lines("method=tools/list")[-2:]))
    checkpoint("one line per call, and the secret never printed.")


def act3() -> None:
    token = mint("weather:read", "weather:write")
    with Server() as s:
        say("A four-year job, submitted as a background task")
        s.call_as_task("build_climate_profile", {"location": "Denver", "date": "2026-11-01", "years": 4}, token)
        say("rain_check with no date: the tool asks instead of guessing")
        answer = s.call_with_elicitation("rain_check", {"location": "Denver"}, token, pick=2)
        say("The tool resumes with the answer", "\n".join(answer.splitlines()[:4]))
        say("Same call, and this time the user declines")
        say("The tool handles it", s.call_with_elicitation("rain_check", {"location": "Denver"}, token, pick=None))
    checkpoint("the agent got a receipt, not a timeout, and the tool asked before it guessed.")


def act4() -> None:
    token = mint("weather:read", "weather:write")
    with Server(view="search") as s:
        say("Tool search on: the whole catalog is two tools", "\n".join(s.list_tools(token)))
        hits = s.call("search_tools", {"query": "rain"}, token)
        say("search_tools('rain'): full definitions for the matches", [h["name"] for h in hits] if isinstance(hits, list) else hits)
    with Server(view="code") as s:
        say("Code mode on: three tools, one of them runs scripts", "\n".join(s.list_tools(token)))
        say("execute: three tool calls in one round trip, only the summary comes back", s.call("execute", {"code": CODE_MODE_SCRIPT}, token))
    checkpoint("twenty tools, two in context.")


def proxy() -> None:
    # The machine identity is handed to the proxy process only; the client below holds no token.
    service_token = mint("weather:read", "weather:write", subject="svc-weather@example.gov")
    with Server(), Server(view="proxy", port=8202, env={"SERVICE_TOKEN": service_token, "BACKEND_URL": f"http://127.0.0.1:{PORT}/mcp"}) as p:
        say("Through the proxy, with no token at all", "\n".join(p.list_tools(None)))
        say("A call through it", p.call("save_favorite_location", {"location": "Denver"}, None))
    checkpoint("the agent never held the credential, and the rule still ran.")


def skill() -> None:
    token = mint("weather:read")
    with Server(file=ROOT / "skills_server.py", port=SKILLS_PORT) as s:
        say("The playbook, served beside the tools (skill://)", s.read_resource("skill://rain-outlook/SKILL.md", token))
    checkpoint("the methodology ships as a skill, not a prompt.")


ACTS = {"1": act1, "2": act2, "3": act3, "4": act4, "proxy": proxy, "skill": skill}

if __name__ == "__main__":
    choice = sys.argv[1] if len(sys.argv) > 1 else ""
    if choice not in ACTS:
        raise SystemExit(__doc__)
    quiet_client_logs()
    ACTS[choice]()
