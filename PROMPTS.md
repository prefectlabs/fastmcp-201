# PROMPTS.md: the talk track, one server, four acts

Terminal A runs `server.py` with its log visible. Terminal B is `claude`,
started from this folder, with one MCP entry, `weather` (written by
`uv run python setup_client.py`). You scroll `server.py` while talking, then
type the prompt. Ctrl+O expands a tool call; Claude Code loads MCP tools
lazily, so each real call is preceded by a `ToolSearch` lookup. `demo.py 1`
to `4` is the fallback for any act.

Rehearsed 2026-10-28 on Claude Code 2.1.312 with every prompt below.

## Act I · Who's calling (12 min)

Code: the `ACT I` banner in `server.py`. `mcp.auth = JWTVerifier(...)`: the
server holds a public key, the identity provider holds the private one.
`@mcp.tool(auth=require_scopes("weather:write"))`: one argument, and the tool
is invisible to anyone without the scope. The token in `.mcp.json` carries
both scopes.

| Type | Audience sees |
|---|---|
| `/mcp` | `weather` connected. Point at terminal A: the first requests. |
| `What tools do you have on weather?` | six tools, `save_favorite_location` among them. Say: a caller with only `weather:read` would see five, and a direct call would fail as "unknown tool". Not hidden by the prompt, hidden by the server. |
| `Save Denver as a favorite location.` | one tool call; the reply names the subject from the token |
| `Read my favorites.` | the agent reads the `weather://favorites` resource, not a tool. Say: saving is an action, so it is a tool; the list is data, so it is a resource, and resources cost the agent nothing until read. |

Say: authentication and authorization are separate, and the second one is one argument per tool.

## Act II · The path, not the prompt (13 min)

Code: the `ACT II` banner. `LoggingMiddleware` writing to the `audit` logger,
then `RedactEmails`, a dozen lines with an `on_call_tool` hook and a
`call_next`. Middleware runs on every call whether the model remembers to or
not. Credentials for a vendor's server live in the environment of a
`ProxyProvider` (the optional block), never in a prompt.

| Type | Audience sees |
|---|---|
| `Save Denver as a favorite again.` | terminal A: `event=request_start method=tools/call ...` then `event=request_success ... duration_ms=`; terminal B: the subject is `[redacted]` |
| `What's the forecast for Denver tomorrow?` | a second pair of log lines, same shape, for a different tool |

Say: one line per call, and the secret never printed.

## Act III · Tools that take time, and tools that ask (14 min)

Code: the `ACT III` banner. `mcp.add_extension(TasksExtension(url="memory://"))`,
`@mcp.tool(task=True)` on an async tool with a `Progress` dependency, and
`rain_check`, which asks for the date instead of guessing. `rain_check` gives
the same answer as `calculate_rain_probability`; the point is the question.
It is written for both protocol eras; the comment above it says which does what.

| Type | Audience sees |
|---|---|
| `Build the climate profile for Denver on 2026-11-01 over 4 years.` | the agent answers at once that the profile is "building in the background" and moves on; seconds later a line like `MCP task <id> (weather/build_climate_profile) completed` and the numbers. That is the receipt-and-poll, driven by Claude Code: the tool returned a task id, the client polled `tasks/get`. (Rehearsed by Wayne in the interactive client on 2.1.312; headless `claude -p` runs the same tool inline, which is why the scripted check never showed it.) |
| `What's the rain outlook for Denver? Use rain_check and don't pass a date.` | the dialog with four dates; pick one; the outlook for that date. Ctrl+O: the call ran twice, the second time carrying your answer. That is the 2026-07-28 shape: the tool returned an `InputRequiredResult`, the client answered and re-ran it. |

Say: the agent got a receipt, not a timeout, and the tool asked before it guessed.

## Act IV · Keep the agent's head clear (12 min)

Code: the `ACT IV` banner. Two more server objects, `search_view` and
`code_view`, wrap the same tools in-process through `FastMCPProvider` with one
transform each. A catalog transform replaces the entire tool list and two of
them cannot stack, which is why they are views and why this act restarts the
process. Same port, same `weather` entry.

Terminal A: Ctrl-C, then `uv run python server.py --view search`. Terminal B: `/mcp` to reconnect.

| Type | Audience sees |
|---|---|
| `What tools do you have on weather?` | two: `search_tools` and `call_tool` |
| `Will it rain in Denver this weekend?` | Ctrl+O: `search_tools` with a natural-language query returns the matching tools with full schemas, then `call_tool` runs them |

Terminal A: Ctrl-C, then `uv run python server.py --view code`. Terminal B: `/mcp` to reconnect.

| Type | Audience sees |
|---|---|
| `What tools do you have on weather?` | three: `search`, `get_schema`, `execute` |
| `For Denver: tomorrow's forecast, last year's temperature on today's date, and the rain chance on 2026-11-05, in one execute call.` | Ctrl+O: `search`, then one `execute` whose `code` is a short script with three `call_tool` lines and a `return`; only the summary comes back |

Say: twenty tools, two in context.

### Optional: the skill (FastMCP 4.2.0a1)

Terminal A: Ctrl-C, then `.venv-skills/bin/python skills_server.py` (same server plus `skills/rain-outlook/SKILL.md`, same port). Terminal B: `/mcp`.

| Type | Audience sees |
|---|---|
| `Will it rain in Denver this weekend? Answer briefly.` | a plain answer, two calls |
| type `@` | `weather:skill://rain-outlook/SKILL.md` in the resource picker |
| `@weather:skill://rain-outlook/SKILL.md will it rain in Denver this weekend?` | the client reads the skill, then five `get_historical_weather` calls per day, then the forecast; the dates on the first line, one percent, umbrella only above 40, and `history: Open-Meteo archive · forecast: Open-Meteo 16-day` as the last line |

Say: this is the climb's stage 04, the playbook served once instead of copied into every laptop.
