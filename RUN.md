# RUN.md: setup once, then four commands

`server.py` is the whole story: the 101 weather server at the top, then four
acts, each a banner comment and the layer it adds, narrated in the comments.
Scroll it while talking. Then play the act:

| Act | Command | Minutes |
|---|---|---|
| I · Who's calling | `uv run python demo.py 1` | 12 |
| II · The path, not the prompt | `uv run python demo.py 2` | 13 |
| III · Tools that take time, and tools that ask | `uv run python demo.py 3` | 14 |
| IV · Keep the agent's head clear | `uv run python demo.py 4` | 12 |

Each command starts `server.py` on port 8201, mints the tokens it needs, plays
the before-and-after sequence with a label per step, and shuts the server
down. One terminal, nothing to export, toggle or paste.

## Setup, once

```bash
uv sync
```

Port 8201 must be free. Optional, for the skill at the end of Act IV (FastMCP 4.2.0a1 in its own venv):

```bash
uv venv .venv-skills && uv pip install --python .venv-skills/bin/python --prerelease=allow "fastmcp[tasks,code-mode]==4.2.0a1" requests && uv pip install --python .venv-skills/bin/python --no-deps -e .
```

## Act I · Who's calling

```bash
uv run python demo.py 1
```

```
>> No token: the door is shut before any tool runs
   HTTP 401   www-authenticate: Bearer

>> Read-only token: the catalog (the 101 three, plus Act III's two)
   get_weather_forecast
   get_historical_weather
   calculate_rain_probability
   build_climate_profile
   rain_check

>> Read-only token calls the write tool anyway
   tool error: Unknown tool: 'save_favorite_location'

>> Token with weather:write: one more tool appears
   get_weather_forecast
   get_historical_weather
   calculate_rain_probability
   save_favorite_location
   build_climate_profile
   rain_check

   new: ['save_favorite_location']

>> Call it
   Saved 'Denver' for [redacted]. Favorites: ['Denver']

Checkpoint: the tool list changed and you didn't touch the tool.
```

(It is one server, so Act III's two tools are already in the list and Act II's
middleware already redacts the email. Say so, or save both observations for
their acts.)

## Act II · The path, not the prompt

```bash
uv run python demo.py 2
```

```
>> Same call as Act I, through the middleware
   Saved 'Denver' for [redacted]. Favorites: ['Denver']

>> The server's audit log for that call, one line in, one line out
   event=request_start method=tools/call source=client payload={... "name":"save_favorite_location","arguments":{"location":"Denver"} ...}
   event=request_success method=tools/call source=client duration_ms=...

>> Every method gets the same shape (tools/list)
   event=request_start method=tools/list source=client payload=...
   event=request_success method=tools/list source=client duration_ms=...

Checkpoint: one line per call, and the secret never printed.
```

Optional, a server you don't own, wrapped with the same middleware and a
service token the agent never sees (the backend is this same server on 8201,
the proxy sits on 8202):

```bash
uv run python demo.py proxy
```

Expect the backend's tools listed with no token, then `Saved 'Denver' for [redacted].`

## Act III · Tools that take time, and tools that ask

```bash
uv run python demo.py 3
```

```
>> A four-year job, submitted as a background task

>> Receipt, back at once
   task_id=...  status=working  poll hint=5000 ms

>> Polling tasks/get
   working    fetching 2025-11-01 (1 of 4)
   working    fetching 2024-11-01 (2 of 4)
   working    fetching 2023-11-01 (3 of 4)
   working    fetching 2022-11-01 (4 of 4)
   completed

>> Result
   { "location": "Denver", "date": "2026-11-01", "years": 4, "rainy_years": ..., "rain_probability_pct": ... }

>> rain_check with no date: the tool asks instead of guessing

>> The server asks
   Which date do you mean for Denver?
   1. <tomorrow>
   2. <day after>
   3. ...
   4. ...

>> The client answers
   2  (<day after>)

>> The tool resumes with the answer
   Rain outlook for Denver, United States on <day after>:
   History: rained on this date in N of the last 5 years (..%).
   ...

>> Same call, and this time the user declines
>> The server asks ...
>> The client answers
   decline
>> The tool handles it
   No date chosen (decline).

Checkpoint: the agent got a receipt, not a timeout, and the tool asked before it guessed.
```

The runner polls faster than the server's five-second hint so the progress
lines are visible. The elicitation runs on the handshake-era protocol, which
is what `ctx.elicit` needs; on 2026-07-28 the tool would return an
`InputRequiredResult` instead.

## Act IV · Keep the agent's head clear

```bash
uv run python demo.py 4
```

```
>> Tool search on: the whole catalog is two tools
   search_tools
   call_tool

>> search_tools('rain'): full definitions for the matches
   [ "rain_check", "calculate_rain_probability", ... ]

>> Code mode on: three tools, one of them runs scripts
   search
   get_schema
   execute

>> execute: three tool calls in one round trip, only the summary comes back
   { "forecast": "...", "last_year": "...", "outlook": "Estimated chance of rain: ..%" }

Checkpoint: twenty tools, two in context.
```

`demo.py 4` serves `search_view` and then `code_view`, the two objects at the
bottom of `server.py` that wrap the main server in-process with a transform
applied. The script it ran is `CODE_MODE_SCRIPT` at the top of `demo.py`.

Optional, the skill, from the second venv:

```bash
.venv-skills/bin/python demo.py skill
```

Expect the SKILL.md text under `>> The playbook, served beside the tools (skill://)`.

## Live, with Claude Code as the client

The four `demo.py` commands are the fallback. The real show is an agent:
terminal A runs the one server with its log visible, terminal B is a Claude
Code session connected to it, and you scroll `server.py` while talking. The
prompts, per act, are in `PROMPTS.md`.

Once, from this folder (the token lasts 24 hours; rerun on the day):

```bash
uv run python setup_client.py
```

That writes `.mcp.json` with a single entry, `weather`, carrying a token with
both scopes. Nothing to export. Terminal A:

```bash
uv run python server.py
```

Terminal B, from this folder:

```bash
claude
```

Then `/mcp`: approve the project server once; `weather` shows connected.
Act IV restarts terminal A with `--view search` and then `--view code` (same
port, same entry; `/mcp` in B reconnects), and the optional skill beat starts
`.venv-skills/bin/python skills_server.py` in its place. Claude Code 2.1.312
drives both Act III shapes interactively: the elicitation dialog, and the
background task ("building in the background", then an `MCP task ... completed`
line). Headless `claude -p` runs task tools inline, so don't judge tasks from a
scripted run. If a connection misbehaves: `claude --debug=mcp`.

## If something goes wrong

- Stopping the server: one Ctrl-C. A second Ctrl-C during the shutdown prints a
  long traceback from the task worker's teardown; harmless, but ugly on screen.
- `port 8201 is busy`: `lsof -nP -iTCP:8201`, stop it, rerun.
- `server exited early`: the log tail is printed; usually a typo in `server.py`.
- Open-Meteo slow or down: Acts I and II never touch it; Act III's task and
  rain_check and Act IV's script do.
- Tests: `uv run pytest -q` runs the in-memory tests and the demo smoke tests
  (those take about a minute and need the network); `uv run pytest -m "not lab"` skips them.
- Token in `.mcp.json` expired: `uv run python setup_client.py` again.
