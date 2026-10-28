"""MCP 201: from a server that works to a server you can govern.

One file, four acts, one server. The top is the FastMCP 101 weather server
exactly as the 101 course left it. Each act below adds one layer to that same
server, and the comments say what each construct does, why it is there, and
the one thing that bites. Scroll and read; then play the act:

    uv run python demo.py 1      Act I    who's calling (authentication, authorization)
    uv run python demo.py 2      Act II   the path, not the prompt (middleware)
    uv run python demo.py 3      Act III  tools that take time, and tools that ask
    uv run python demo.py 4      Act IV   keep the agent's head clear (search, code mode)

demo.py starts this file on port 8201, mints the tokens it needs, plays the
before-and-after sequence with labeled output, and shuts the server down.
Nothing to export, toggle or uncomment.
"""


# =============================================================================
# WHERE 101 LEFT YOU: the weather server, unchanged
# =============================================================================
# Three tools, one resource, one prompt, all calling Open-Meteo (free, no key).
# Nothing below this banner changed since the 101 course. The four acts start
# at the next banner.

from datetime import datetime, timedelta

import requests
from fastmcp import FastMCP

# The server object. Every tool, resource, and prompt registers against it.
# Everything in the four acts attaches to this same object.
mcp = FastMCP("Weather Server")

FORECAST_URL = "https://api.open-meteo.com/v1/forecast"
ARCHIVE_URL = "https://archive-api.open-meteo.com/v1/archive"
GEOCODE_URL = "https://geocoding-api.open-meteo.com/v1/search"
DAILY_FIELDS = "temperature_2m_max,temperature_2m_min,precipitation_sum,weather_code"


def _geocode_location(location: str) -> dict | None:
    """Turn a place name into coordinates using Open-Meteo's geocoder."""
    params = {"name": location, "count": 1, "language": "en", "format": "json"}
    try:
        response = requests.get(GEOCODE_URL, params=params, timeout=10)
        response.raise_for_status()
        results = response.json().get("results")
    except requests.RequestException:
        return None
    if not results:
        return None
    hit = results[0]
    return {
        "latitude": hit["latitude"],
        "longitude": hit["longitude"],
        "name": hit["name"],
        "country": hit.get("country", ""),
    }


def _describe_weather_code(code: int) -> str:
    """Translate a WMO weather code into plain English."""
    codes = {
        0: "Clear", 1: "Mainly clear", 2: "Partly cloudy", 3: "Overcast",
        45: "Foggy", 48: "Foggy", 51: "Light drizzle", 53: "Drizzle",
        55: "Heavy drizzle", 61: "Light rain", 63: "Rain", 65: "Heavy rain",
        71: "Light snow", 73: "Snow", 75: "Heavy snow", 77: "Snow grains",
        80: "Light showers", 81: "Showers", 82: "Heavy showers",
        85: "Light snow showers", 86: "Snow showers", 95: "Thunderstorm",
        96: "Thunderstorm with hail", 99: "Thunderstorm with hail",
    }
    return codes.get(code, "Unknown")


@mcp.tool
def get_weather_forecast(location: str, days_ahead: int = 7) -> str:
    """Get the daily weather forecast for a location, up to 16 days ahead.

    Args:
        location: City or place name, for example "Washington" or "Denver".
        days_ahead: How many days to forecast, from 1 to 16. Defaults to 7.
    """
    if days_ahead < 1 or days_ahead > 16:
        return "Error: days_ahead must be between 1 and 16."

    coords = _geocode_location(location)
    if not coords:
        return f"Error: could not find a location called '{location}'."

    params = {
        "latitude": coords["latitude"],
        "longitude": coords["longitude"],
        "daily": DAILY_FIELDS,
        "forecast_days": days_ahead,
        "temperature_unit": "fahrenheit",
        "precipitation_unit": "inch",
    }
    try:
        response = requests.get(FORECAST_URL, params=params, timeout=10)
        response.raise_for_status()
        daily = response.json()["daily"]
    except requests.RequestException as exc:
        return f"Error fetching forecast: {exc}"

    lines = [f"Forecast for {coords['name']}, {coords['country']} ({days_ahead} days):", ""]
    for i in range(days_ahead):
        lines.append(
            f"{daily['time'][i]}: {daily['temperature_2m_min'][i]}-{daily['temperature_2m_max'][i]} F, "
            f"{_describe_weather_code(daily['weather_code'][i])}, "
            f"precipitation {daily['precipitation_sum'][i]} in"
        )
    return "\n".join(lines)


@mcp.tool
def get_historical_weather(location: str, date: str) -> str:
    """Get the recorded weather for a location on a past date.

    Args:
        location: City or place name, for example "Washington" or "Denver".
        date: The date to look up, in YYYY-MM-DD format, for example "2023-07-04".
    """
    try:
        target = datetime.strptime(date, "%Y-%m-%d")
    except ValueError:
        return f"Error: '{date}' is not a valid date. Use YYYY-MM-DD."
    if target > datetime.now():
        return f"Error: {date} is in the future. Use get_weather_forecast for future dates."
    if target < datetime.now() - timedelta(days=365 * 80):
        return f"Error: {date} is too far back. History covers roughly the last 80 years."

    coords = _geocode_location(location)
    if not coords:
        return f"Error: could not find a location called '{location}'."

    params = {
        "latitude": coords["latitude"],
        "longitude": coords["longitude"],
        "start_date": date,
        "end_date": date,
        "daily": DAILY_FIELDS,
        "temperature_unit": "fahrenheit",
        "precipitation_unit": "inch",
    }
    try:
        response = requests.get(ARCHIVE_URL, params=params, timeout=10)
        response.raise_for_status()
        daily = response.json()["daily"]
    except requests.RequestException as exc:
        return f"Error fetching historical weather: {exc}"

    precip = daily["precipitation_sum"][0]
    rained = f"It rained ({precip} in)." if precip and precip > 0 else "No precipitation recorded."
    return (
        f"Weather in {coords['name']}, {coords['country']} on {date}:\n"
        f"Temperature: {daily['temperature_2m_min'][0]}-{daily['temperature_2m_max'][0]} F\n"
        f"Conditions: {_describe_weather_code(daily['weather_code'][0])}\n"
        f"{rained}"
    )


@mcp.tool
def calculate_rain_probability(location: str, date: str) -> str:
    """Estimate the chance of rain on a future date, up to 16 days ahead.

    Combines the last five years of history for that calendar date with the
    current forecast, so the answer is grounded in both patterns and prediction.

    Args:
        location: City or place name, for example "Washington" or "Denver".
        date: The future date to assess, in YYYY-MM-DD format.
    """
    try:
        target = datetime.strptime(date, "%Y-%m-%d").date()
    except ValueError:
        return f"Error: '{date}' is not a valid date. Use YYYY-MM-DD."
    today = datetime.now().date()
    if target < today:
        return f"Error: {date} is in the past. Use get_historical_weather for past dates."
    days_ahead = (target - today).days
    if days_ahead > 16:
        return f"Error: {date} is more than 16 days away, which is as far as forecasts go."

    coords = _geocode_location(location)
    if not coords:
        return f"Error: could not find a location called '{location}'."

    # Same calendar date, each of the last five years.
    history = []
    for years_back in range(1, 6):
        past = target.replace(year=target.year - years_back).isoformat()
        params = {
            "latitude": coords["latitude"],
            "longitude": coords["longitude"],
            "start_date": past,
            "end_date": past,
            "daily": "precipitation_sum",
            "precipitation_unit": "inch",
        }
        try:
            response = requests.get(ARCHIVE_URL, params=params, timeout=10)
            response.raise_for_status()
            value = response.json()["daily"]["precipitation_sum"][0]
        except (requests.RequestException, KeyError, IndexError):
            continue
        if value is not None:
            history.append(value)

    lines = [f"Rain outlook for {coords['name']}, {coords['country']} on {date}:", ""]

    historical_prob = None
    if history:
        rainy_years = sum(1 for p in history if p > 0.01)
        historical_prob = rainy_years / len(history) * 100
        lines.append(
            f"History: rained on this date in {rainy_years} of the last {len(history)} years "
            f"({historical_prob:.0f}%)."
        )
    else:
        lines.append("History: not available.")

    # Forecast for the target day.
    forecast_precip = None
    params = {
        "latitude": coords["latitude"],
        "longitude": coords["longitude"],
        "daily": "precipitation_sum",
        "forecast_days": min(days_ahead + 1, 16),
        "precipitation_unit": "inch",
    }
    try:
        response = requests.get(FORECAST_URL, params=params, timeout=10)
        response.raise_for_status()
        forecast_precip = response.json()["daily"]["precipitation_sum"][days_ahead]
    except (requests.RequestException, KeyError, IndexError):
        pass

    if forecast_precip is not None:
        verdict = "rain likely" if forecast_precip > 0.01 else "no rain expected"
        lines.append(f"Forecast: {forecast_precip:.2f} in of precipitation, {verdict}.")
    else:
        lines.append("Forecast: not available.")

    # Blend the two signals. Forecast counts more when it predicts rain.
    if historical_prob is not None and forecast_precip is not None:
        forecast_weight = 0.4 if forecast_precip > 0.01 else 0.2
        forecast_signal = 100 if forecast_precip > 0.01 else 0
        combined = historical_prob * (1 - forecast_weight) + forecast_signal * forecast_weight
    elif historical_prob is not None:
        combined = historical_prob
    else:
        lines.append("")
        lines.append("Not enough data to estimate a probability.")
        return "\n".join(lines)

    lines.append("")
    lines.append(f"Estimated chance of rain: {combined:.0f}%")
    if combined >= 70:
        lines.append("High. Plan for rain.")
    elif combined >= 40:
        lines.append("Moderate. Have a backup plan.")
    else:
        lines.append("Low. Looks promising.")
    return "\n".join(lines)


# The 101 resource (something to read) and prompt (a saved recipe).


@mcp.resource("weather://about")
def about() -> str:
    """Explain what this server does and where its data comes from."""
    return (
        "Weather Server answers forecast, history, and rain-probability questions. "
        "Data comes from Open-Meteo (open-meteo.com), a free and open weather API. "
        "Forecasts reach 16 days ahead; history covers roughly 80 years."
    )


@mcp.prompt
def plan_outdoor_event(location: str, date: str) -> str:
    """Ask the assistant to decide whether an outdoor event should keep its date."""
    return (
        f"I'm planning an outdoor event in {location} on {date}. "
        "Check the chance of rain and the forecast, then tell me plainly whether "
        "to keep the date or pick a backup, and why."
    )


# =============================================================================
# ACT I · WHO'S CALLING                                   (demo.py 1, ~12 min)
# =============================================================================
# The room asked: "How do we control which tools a server exposes and what
# they're authorized to do?" That is two questions. Who are you: authentication.
# What may you do: authorization. FastMCP keeps them separate on purpose.
#
# What demo.py 1 shows: with no token the server answers 401 before any tool
# code runs. A read-only token lists the catalog (the 101 three plus Act III's
# two, since this is one server) and cannot call save_favorite_location. A
# token carrying weather:write sees one more tool and the call goes through.
# Same server, nothing about the tool changed.

from fastmcp.server.auth import require_scopes
from fastmcp.server.auth.providers.jwt import JWTVerifier
from fastmcp.server.dependencies import get_access_token

from weather.keys import AUDIENCE, ISSUER, ensure_keypair

# Authentication. Someone else, the identity provider, signs tokens with a
# private key. We hold only the public key (keys/public.pem, made on first
# run) and check signature, issuer, audience and expiry on every HTTP request.
# With a real IdP, replace public_key= with jwks_uri= and keys rotate themselves.
# Gotcha: HTTP defaults to auth=None. Over stdio, auth is skipped entirely.
auth = JWTVerifier(
    public_key=ensure_keypair().public_key,
    issuer=ISSUER,
    audience=AUDIENCE,
    algorithm="RS256",
)
mcp.auth = auth


# Authorization, one argument. A caller whose token lacks weather:write never
# sees this tool in the list, and a direct call fails as "unknown tool".
# Gotcha: auth= on a tool hides. To deny with the missing scope named instead,
# use AuthMiddleware(restrict_tag(...)) from fastmcp.server.middleware.authorization.
FAVORITES: dict[str, list[str]] = {}  # per caller, for the life of the process


def _caller() -> str:
    token = get_access_token()  # the verified token, claims and all
    return token.claims["sub"] if token else "anonymous"


@mcp.tool(auth=require_scopes("weather:write"))
def save_favorite_location(location: str) -> str:
    """Save a location to the caller's favorites list. Read the list back from weather://favorites."""
    who = _caller()
    favorites = FAVORITES.setdefault(who, [])
    if location not in favorites:
        favorites.append(location)
    return f"Saved {location!r} for {who}. Favorites: {favorites}"


# The read side is a resource, not a tool: saving is an action, reading the
# list back is data. Resources cost the agent nothing until it reads them.
# Any authenticated caller can read their own list; only weather:write can add.
@mcp.resource("weather://favorites")
def favorites() -> str:
    """The caller's saved favorite locations, one per line."""
    saved = FAVORITES.get(_caller(), [])
    return "\n".join(saved) if saved else "No favorites saved yet. Use save_favorite_location."


# =============================================================================
# ACT II · THE PATH, NOT THE PROMPT                       (demo.py 2, ~13 min)
# =============================================================================
# The room asked: "How do we keep service-account credentials safe in a hosted
# server, and can we see what every call did?" Put the rule in the path of the
# request, not in the prompt. Middleware runs on every call whether the model
# remembers to or not, and credentials stay in the server's environment.
#
# What demo.py 2 shows: the same save call as Act I, but the caller's email
# comes back as [redacted]. Then the server's own audit log for that call: one
# line on the way in, one on the way out, and the same two lines for every
# other method. No tool changed.

import json
import logging
import os
import re

from fastmcp.server.middleware import Middleware
from fastmcp.server.middleware.logging import LoggingMiddleware
from fastmcp.tools import ToolResult
from mcp_types import TextContent

# Built in. One line on the way in, one on the way out, for tools/call,
# tools/list, everything. It writes to a plain "audit" logger so each entry is
# one line; swap in StructuredLoggingMiddleware for JSON a SIEM can index.
# Gotcha: first added runs first on the way in and last on the way out.
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(message)s")
audit_log = LoggingMiddleware(logger=logging.getLogger("audit"), include_payloads=True, max_payload_length=120)
mcp.add_middleware(audit_log)

EMAIL = re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+")


# Ours. A middleware is a class with a hook and a call_next. Skip call_next
# and the request stops. Everything a tool returns passes through here, so no
# email address ever leaves the server, in text or in structured output.
# Gotcha: once tasks are on (Act III) this hook also sees task receipts, which
# carry no content. The isinstance line lets them through untouched.
class RedactEmails(Middleware):
    async def on_call_tool(self, context, call_next):
        result = await call_next(context)
        if isinstance(result, ToolResult):
            for block in result.content:
                if isinstance(block, TextContent):
                    block.text = EMAIL.sub("[redacted]", block.text)
            if result.structured_content:
                scrubbed = EMAIL.sub("[redacted]", json.dumps(result.structured_content))
                result.structured_content = json.loads(scrubbed)
        return result


redact = RedactEmails()
mcp.add_middleware(redact)

# Optional (demo.py proxy): a server you don't own, wrapped the same way.
# ProxyProvider fetches a backend's catalog and forwards every call through a
# ProxyClient carrying a service-account token that lives in this process's
# environment and nowhere else. The agent never reaches the backend and never
# sees the token, and the same middleware runs in front of every forwarded call.
# Gotcha: the deck says FastMCP.as_proxy; on 4.1.4 it is ProxyProvider from
# fastmcp.server.providers.proxy. Background tasks cannot run through a proxy.
from fastmcp.server.providers.proxy import ProxyClient, ProxyProvider

BACKEND_URL = os.environ.get("BACKEND_URL", "http://127.0.0.1:8201/mcp")
proxy = FastMCP(
    "Governed Weather (proxy)",
    providers=[ProxyProvider(lambda: ProxyClient(BACKEND_URL, auth=os.environ.get("SERVICE_TOKEN")))],
    middleware=[audit_log, redact],
)


# =============================================================================
# ACT III · TOOLS THAT TAKE TIME, AND TOOLS THAT ASK      (demo.py 3, ~14 min)
# =============================================================================
# The room asked: "Our jobs take minutes, not seconds. And sometimes the tool
# needs to ask a question." Agents don't wait well: a four-minute tool holds a
# connection and burns the turn. The 2026 protocol has a shape for each.
#
# What demo.py 3 shows: build_climate_profile hands back a task id in under a
# second, the poll prints a "fetching <year>" line per year, then the result.
# rain_check with no date asks which date you mean; the client answers option
# 2 and the tool finishes. A second run declines, and the tool says so. The
# runner uses the handshake era; Claude Code uses the 2026 shape. Same tool.

import asyncio
from datetime import date as date_type

from fastmcp import Context
from fastmcp.server.dependencies import Progress
from fastmcp_tasks import TasksExtension

# One line turns on background execution for tools marked task=True.
# memory:// runs the worker inside this process and forgets on restart.
# redis:// persists, and workers can scale in their own processes.
# Gotcha: TasksExtension lives in its own package, fastmcp_tasks ("fastmcp[tasks]").
mcp.add_extension(TasksExtension(url="memory://"))


# task=True: the call returns a receipt and the work runs in the worker. The
# tool must be async. Progress is injected; every set_message shows up in the
# client's poll as the task's status message.
# Gotcha: ctx.elicit raises inside a task. Ask first, then start the task.
@mcp.tool(task=True)
async def build_climate_profile(location: str, date: str, years: int = 5, progress: Progress = Progress()) -> dict:
    """Same calendar date across the last N years, one archive call per year, so it is slow.

    Returns the place it resolved to, the dates it rained, and the share of years with rain.
    """
    target = date_type.fromisoformat(date)
    coords = _geocode_location(location)  # the 101 helper; say which place we mean
    resolved = f"{coords['name']}, {coords['country']}" if coords else location
    await progress.set_total(years)
    rainy_dates = []
    for back in range(1, years + 1):
        past = target.replace(year=target.year - back).isoformat()
        await progress.set_message(f"fetching {past} ({back} of {years})")
        report = await asyncio.to_thread(get_historical_weather, location, past)  # the 101 tool, as a function
        if "It rained" in report:
            rainy_dates.append(past)
        await progress.increment()
    return {"location": resolved, "date": date, "years": years, "rainy_years": len(rainy_dates),
            "rainy_dates": rainy_dates, "rain_probability_pct": round(100 * len(rainy_dates) / years)}


# The tool asks instead of guessing. Two protocol eras, one tool:
#   * Handshake era (2025-11-25 and earlier): ctx.elicit pauses the tool, the
#     client shows the question, the tool resumes with accept/decline/cancel.
#   * 2026-07-28 era (Claude Code 2.1.3xx, fastmcp.Client by default): there
#     are no server-initiated requests, so ctx.elicit raises before the wire.
#     The tool then returns an InputRequiredResult; the client answers and
#     re-runs the call with input_responses attached, and the tool reads them.
# Gotcha: ctx.elicit also raises inside a task. Ask first, then start the
# task. Options must be strings.

import mcp_types
from fastmcp.exceptions import ToolError


def _upcoming_dates() -> list[str]:
    today = date_type.today()
    return [(today + timedelta(days=d)).isoformat() for d in (1, 2, 3, 7)]


@mcp.tool
async def rain_check(location: str, ctx: Context, date: str | None = None) -> str | mcp_types.InputRequiredResult:
    """Chance of rain for a location on an upcoming date; asks which date if none is given.

    Same answer as calculate_rain_probability. The difference is the question:
    this tool asks for the missing date instead of guessing or failing.
    """
    question = f"Which date do you mean for {location}?"
    if date is None and ctx.input_responses is not None:  # 2026 era, second round: the answer is attached
        answer = ctx.input_responses["date"]
        if answer.action != "accept":
            return f"No date chosen ({answer.action})."
        date = answer.content["value"]
    if date is None:
        try:  # handshake era: pause here until the client answers
            answer = await ctx.elicit(question, response_type=_upcoming_dates())
        except ToolError:  # 2026 era: no back-channel, so hand the question back instead
            return mcp_types.InputRequiredResult(
                input_requests={"date": mcp_types.ElicitRequest(params=mcp_types.ElicitRequestFormParams(
                    message=question,
                    requested_schema={"type": "object", "properties": {"value": {"type": "string", "enum": _upcoming_dates()}}, "required": ["value"]},
                ))},
            )
        if answer.action != "accept":
            return f"No date chosen ({answer.action})."
        date = answer.data
    return calculate_rain_probability(location, date)  # the 101 tool, as a function


# =============================================================================
# ACT IV · KEEP THE AGENT'S HEAD CLEAR                    (demo.py 4, ~12 min)
# =============================================================================
# The room asked: "Don't resources and prompts just bloat the context window?"
# No: those cost nothing until the agent reads them. Tool definitions cost on
# every turn. Every tool you ship is rent in the agent's head, and these two
# transforms change what the agent sees without changing what it may call.
#
# What demo.py 4 shows: the catalog drops to search_tools and call_tool, and a
# search for "rain" surfaces the right tools with their full definitions. Then
# code mode: three tools (search, get_schema, execute), and one execute call
# runs a three-tool script with only the final answer coming back.

from fastmcp.experimental.transforms.code_mode import CodeMode
from fastmcp.server.providers import FastMCPProvider
from fastmcp.server.transforms.search import BM25SearchTransform

# A catalog transform replaces the whole tool list, which would break Act I's
# "three tools, then four". So the transforms live on two more server objects
# that serve the same tools through FastMCPProvider (in-process, no network):
# demo.py 4 starts search_view and then code_view; demo.py 1 to 3 start mcp.
# Verified on 4.1.4: scope filtering and the caller's identity carry through a
# view; the backend's middleware does not, so the views get the same two. And
# a view that lists a task=True tool must register its own TasksExtension or
# it refuses to start, so each view gets one.
#
# Tool search: the catalog collapses to two tools. search_tools(query) ranks
# the real tools and returns full definitions for the matches; call_tool(name,
# arguments) runs one. Auth and visibility still apply to what search returns.
# Gotcha: import from fastmcp.server.transforms.search, not the package root.
search_view = FastMCP(
    "Weather Server (tool search)",
    auth=auth,
    providers=[FastMCPProvider(mcp)],
    middleware=[audit_log, redact],
    transforms=[BM25SearchTransform(max_results=3)],
)
search_view.add_extension(TasksExtension(url="memory://"))

# Code mode (experimental): the catalog becomes search / get_schema / execute.
# The agent writes a short Python script that runs in a sandbox (Monty).
# Inside it, call_tool(name, {...}) takes a dict, and the script must `return`
# its answer. Intermediate data never enters the context; the return value does.
# Gotcha: the deck's "Search / GetSchemas" are named search and get_schema here.
code_view = FastMCP(
    "Weather Server (code mode)",
    auth=auth,
    providers=[FastMCPProvider(mcp)],
    middleware=[audit_log, redact],
    transforms=[CodeMode()],
)
code_view.add_extension(TasksExtension(url="memory://"))

# Skills (FastMCP 4.2.0a1) are in skills_server.py, which imports this server
# and adds one SKILL.md from skills/rain-outlook. The alpha never touches this file.


# =============================================================================
# RUNNING IT
# =============================================================================
# One process, one port (8201), one entry in .mcp.json. --view picks which
# object answers on that port: mcp by default (Acts I to III); search_view or
# code_view for Act IV (restart with the flag, same port, same entry); proxy
# for the optional proxy demo. demo.py starts this file the same way.
#
#   uv run python server.py                   Acts I to III
#   uv run python server.py --view search     Act IV, tool search
#   uv run python server.py --view code       Act IV, code mode
if __name__ == "__main__":
    from lab import serve

    serve({"plain": mcp, "search": search_view, "code": code_view, "proxy": proxy})
