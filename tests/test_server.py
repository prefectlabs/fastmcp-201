"""In-memory tests for server.py: no network, no subprocess, no port."""

import pytest
from fastmcp import Client
from fastmcp.client.elicitation import ElicitResult
from fastmcp.exceptions import ToolError
from fastmcp_tasks import call_tool_task

from conftest import as_caller
import server

READ = ["weather:read"]
WRITE = ["weather:read", "weather:write"]


@pytest.fixture
def offline(monkeypatch):
    """The two 101 functions the acts reuse, answered without Open-Meteo."""
    monkeypatch.setattr(server, "get_historical_weather", lambda location, date: "It rained (0.3 in)." if int(date[:4]) % 2 else "No precipitation recorded.")
    monkeypatch.setattr(server, "_geocode_location", lambda location: {"latitude": 0, "longitude": 0, "name": location, "country": "US"})
    monkeypatch.setattr(server, "calculate_rain_probability", lambda location, date: f"Rain outlook for {location} on {date}: 40%")


# Act I
async def test_scope_changes_the_tool_list():
    with as_caller(READ):
        async with Client(server.mcp) as client:
            read_only = {t.name for t in await client.list_tools()}
            with pytest.raises(ToolError, match="Unknown tool"):
                await client.call_tool("save_favorite_location", {"location": "Denver"})
    with as_caller(WRITE, subject="writer@example.gov"):
        async with Client(server.mcp) as client:
            read_write = {t.name for t in await client.list_tools()}
            saved = await client.call_tool("save_favorite_location", {"location": "Denver"})
    assert "save_favorite_location" not in read_only
    assert "save_favorite_location" in read_write
    assert read_write - read_only == {"save_favorite_location"}
    assert saved.data.startswith("Saved 'Denver' for [redacted].")  # Act II's middleware is on the same server


async def test_favorites_resource_reads_back_what_the_tool_saved():
    with as_caller(WRITE, subject="fan@example.gov"):
        async with Client(server.mcp) as client:
            before = (await client.read_resource("weather://favorites"))[0].text
            await client.call_tool("save_favorite_location", {"location": "Denver"})
            await client.call_tool("save_favorite_location", {"location": "Denver"})  # no duplicates
            after = (await client.read_resource("weather://favorites"))[0].text
    assert "No favorites" in before
    assert after == "Denver"


# Act II
async def test_redaction_covers_structured_output():
    with as_caller(WRITE, subject="writer@example.gov"):
        async with Client(server.mcp) as client:
            result = await client.call_tool("save_favorite_location", {"location": "Denver"})
    assert "writer@" not in str(result.structured_content)


# Act III
async def test_task_receipt_progress_result(offline):
    with as_caller(READ):
        async with Client(server.mcp) as client:
            task = await call_tool_task(client, "build_climate_profile", {"location": "Denver", "date": "2026-11-01", "years": 4})
            assert task.create_result.status in {"submitted", "working"}
            messages = set()
            while True:
                status = await task.status()
                if status.status_message:
                    messages.add(status.status_message)
                if status.status in {"completed", "failed", "cancelled"}:
                    break
            assert status.status == "completed"
            result = await task.result()
    assert result.data["rainy_years"] == 2 and result.data["rain_probability_pct"] == 50
    assert result.data["location"] == "Denver, US" and result.data["rainy_dates"] == ["2025-11-01", "2023-11-01"]
    assert any(m.startswith("fetching 20") for m in messages), messages


async def test_plain_call_drives_the_task_and_passes_the_middleware(offline):
    with as_caller(READ):
        async with Client(server.mcp) as client:
            result = await client.call_tool("build_climate_profile", {"location": "Denver", "date": "2026-11-01", "years": 2})
    assert result.data["years"] == 2


async def test_elicitation_asks_then_answers(offline):
    asked = []

    async def handler(message, response_type, params, context):
        asked.append(message)
        return {"value": params.requested_schema["properties"]["value"]["enum"][1]}

    with as_caller(READ):
        async with Client(server.mcp, mode="legacy", elicitation_handler=handler) as client:
            result = await client.call_tool("rain_check", {"location": "Denver"})
    assert asked == ["Which date do you mean for Denver?"]
    assert result.data.startswith("Rain outlook for Denver on 20")


async def test_elicitation_decline(offline):
    async def decline(message, response_type, params, context):
        return ElicitResult(action="decline")

    with as_caller(READ):
        async with Client(server.mcp, mode="legacy", elicitation_handler=decline) as client:
            result = await client.call_tool("rain_check", {"location": "Denver"})
    assert result.data == "No date chosen (decline)."


async def test_elicitation_round_trips_on_the_2026_protocol(offline):
    asked = []

    async def handler(message, response_type, params, context):
        asked.append(message)
        return {"value": params.requested_schema["properties"]["value"]["enum"][1]}

    with as_caller(READ):
        async with Client(server.mcp, elicitation_handler=handler) as client:
            assert client.protocol_version == "2026-07-28"
            result = await client.call_tool("rain_check", {"location": "Denver"})
    assert asked == ["Which date do you mean for Denver?"]
    assert result.data.startswith("Rain outlook for Denver on 20")


async def test_elicitation_decline_on_the_2026_protocol(offline):
    async def decline(message, response_type, params, context):
        return ElicitResult(action="decline")

    with as_caller(READ):
        async with Client(server.mcp, elicitation_handler=decline) as client:
            result = await client.call_tool("rain_check", {"location": "Denver"})
    assert result.data == "No date chosen (decline)."


# Act IV
async def test_search_view_collapses_the_catalog_and_keeps_scopes():
    with as_caller(READ):
        async with Client(server.search_view) as client:
            names = {t.name for t in await client.list_tools()}
            hits = (await client.call_tool("search_tools", {"query": "rain favorite save"})).data
    assert names == {"search_tools", "call_tool"}
    hit_names = {h["name"] for h in hits}
    assert "rain_check" in hit_names or "calculate_rain_probability" in hit_names
    assert "save_favorite_location" not in hit_names  # hidden from a read-only caller, even through search


async def test_code_view_runs_a_script(offline):
    with as_caller(READ):
        async with Client(server.code_view) as client:
            names = {t.name for t in await client.list_tools()}
            result = await client.call_tool("execute", {"code": 'r = await call_tool("get_weather_forecast", {"location": "x", "days_ahead": 99})\nreturn {"n": len(r["result"])}'})
    assert names == {"search", "get_schema", "execute"}
    assert result.data["n"] > 0  # the offline validation message came back as the result
