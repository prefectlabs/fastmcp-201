"""Plumbing for demo.py: start server.py in a subprocess, mint tokens, talk to it, print steps.

Nothing in here is part of the lesson. demo.py is what you read for the
sequence; this file is how it runs.
"""

import asyncio
import json
import os
import socket
import subprocess
import sys
import tempfile
import textwrap
import time
from pathlib import Path

import requests
from fastmcp import Client
from fastmcp.client.elicitation import ElicitResult
from fastmcp.exceptions import ToolError
from fastmcp_tasks import call_tool_task  # registers client task support; import before any Client

ROOT = Path(__file__).resolve().parent
SERVER_FILE = ROOT / "server.py"
PORT = 8201
COMPACT_PORT = 8202
SKILLS_PORT = 8203


# ---------------------------------------------------------------- printing --
def say(label: str, body="") -> None:
    print(f"\n>> {label}")
    if body != "":
        text = json.dumps(body, indent=2) if isinstance(body, (dict, list)) else str(body)
        print(textwrap.indent(text.rstrip(), "   "))


def checkpoint(text: str) -> None:
    print(f"\nCheckpoint: {text}\n")


def quiet_client_logs() -> None:
    """server.py configures logging at import; keep the client's HTTP chatter out of the output."""
    import logging

    for name in ("httpx", "httpx2", "mcp.client", "fastmcp"):
        logging.getLogger(name).setLevel(logging.WARNING)


# ------------------------------------------------------------------ tokens --
def mint(*scopes: str, subject: str = "wayne@example.gov", ttl: int = 3600) -> str:
    """Play the identity provider. The key pair lives in keys/ (made on first use)."""
    from weather.keys import AUDIENCE, ISSUER, ensure_keypair

    return ensure_keypair().create_token(
        subject=subject, issuer=ISSUER, audience=AUDIENCE, scopes=list(scopes), expires_in_seconds=ttl,
        additional_claims={"email": subject, "agency": "GSA"},
    )


# ------------------------------------------------------------------ server --
def _port_open(port: int) -> bool:
    with socket.socket() as sock:
        sock.settimeout(0.2)
        return sock.connect_ex(("127.0.0.1", port)) == 0


class Server:
    """server.py as an HTTP server in a subprocess, for the duration of a with-block."""

    def __init__(self, view: str = "plain", port: int = PORT, env: dict | None = None, file: Path = SERVER_FILE):
        self.cmd = [sys.executable, str(file), "--view", view]
        self.port = port
        self.extra_env = env or {}
        self.url = f"http://127.0.0.1:{port}/mcp"

    def __enter__(self) -> "Server":
        deadline = time.time() + 5
        while _port_open(self.port) and time.time() < deadline:
            time.sleep(0.2)
        if _port_open(self.port):
            raise SystemExit(f"port {self.port} is busy; stop whatever is listening there and rerun")
        self.logfile = tempfile.NamedTemporaryFile("w+", prefix="demo-server-", suffix=".log", delete=False)
        env = {**os.environ, "PORT": str(self.port), "COLUMNS": "200", "PYTHONUNBUFFERED": "1", **self.extra_env}
        self.proc = subprocess.Popen(self.cmd, stdout=self.logfile, stderr=subprocess.STDOUT, cwd=ROOT, env=env)
        deadline = time.time() + 30
        while time.time() < deadline:
            if self.proc.poll() is not None:
                raise SystemExit(f"server exited early:\n{self.log()[-2000:]}")
            if _port_open(self.port):
                time.sleep(0.3)
                return self
            time.sleep(0.2)
        raise SystemExit(f"server did not start in time:\n{self.log()[-2000:]}")

    def __exit__(self, *exc) -> None:
        self.proc.terminate()
        try:
            self.proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            self.proc.kill()
        self.logfile.close()
        os.unlink(self.logfile.name)

    def log(self) -> str:
        self.logfile.flush()
        return Path(self.logfile.name).read_text()

    def audit_lines(self, needle: str) -> list[str]:
        """The server's audit-logger entries containing `needle`, without the timestamp prefix."""
        return [line.split(" audit ", 1)[-1].rstrip() for line in self.log().splitlines() if " audit " in line and needle in line]

    # client helpers, all against this server
    def _client(self, token: str | None, **kw) -> Client:
        return Client(self.url, auth=token, **kw)

    def http_status(self, token: str | None = None) -> str:
        headers = {"Authorization": f"Bearer {token}"} if token else {}
        response = requests.get(self.url, headers=headers, timeout=10)
        challenge = response.headers.get("www-authenticate", "")
        return f"HTTP {response.status_code}" + (f"   www-authenticate: {challenge}" if challenge else "")

    def list_tools(self, token: str | None) -> list[str]:
        async def go():
            async with self._client(token) as client:
                return [t.name for t in await client.list_tools()]

        return asyncio.run(go())

    def call(self, name: str, args: dict, token: str | None):
        async def go():
            async with self._client(token) as client:
                try:
                    result = await client.call_tool(name, args)
                except ToolError as exc:
                    return f"tool error: {exc}"
                return result.data if result.data is not None else result.content[0].text

        return asyncio.run(go())

    def read_resource(self, uri: str, token: str | None) -> str:
        async def go():
            async with self._client(token) as client:
                return (await client.read_resource(uri))[0].text

        return asyncio.run(go())

    def call_as_task(self, name: str, args: dict, token: str) -> None:
        """Submit, print the receipt, poll (faster than the server's hint, so progress shows), print the result."""

        async def go():
            async with self._client(token) as client:
                task = await call_tool_task(client, name, args)
                receipt = task.create_result
                say("Receipt, back at once", f"task_id={task.task_id}  status={receipt.status}  poll hint={receipt.poll_interval_ms} ms")
                seen, lines = None, []
                while True:
                    status = await task.status()
                    line = f"{status.status:<10} {status.status_message or ''}".rstrip()
                    if line != seen:
                        lines.append(line)
                        seen = line
                    if status.status in ("completed", "failed", "cancelled"):
                        break
                    await asyncio.sleep(0.4)
                say("Polling tasks/get", "\n".join(lines))
                result = await task.result()
                say("Result", result.data if result.data is not None else result.content[0].text)

        asyncio.run(go())

    def call_with_elicitation(self, name: str, args: dict, token: str, pick: int | None):
        """Handshake-era client: answer the server's question with option `pick`, or decline."""

        async def handler(message, response_type, params, context):
            options = params.requested_schema["properties"]["value"].get("enum", [])
            say("The server asks", message + "\n" + "\n".join(f"{i}. {o}" for i, o in enumerate(options, 1)))
            if pick is None:
                say("The client answers", "decline")
                return ElicitResult(action="decline")
            say("The client answers", f"{pick}  ({options[pick - 1]})")
            return {"value": options[pick - 1]}

        async def go():
            async with self._client(token, mode="legacy", elicitation_handler=handler) as client:
                return (await client.call_tool(name, args)).data

        return asyncio.run(go())


def serve(views: dict) -> None:
    """The subprocess side: server.py calls this with its servable objects; --view picks one."""
    name = sys.argv[sys.argv.index("--view") + 1] if "--view" in sys.argv else "plain"
    if name == "compact":
        serve_compact(views["search"], views["code"], port=int(os.environ.get("PORT", PORT)))
        return
    views[name].run(transport="http", port=int(os.environ.get("PORT", PORT)), show_banner=False)


def serve_compact(search_view, code_view, port: int) -> None:
    """One process, one port, two catalogs: /search/mcp (tool search) and /code/mcp (code mode).

    Each FastMCP object becomes a Starlette sub-app; their lifespans (which
    start the task workers) are entered together.
    """
    import contextlib

    import uvicorn
    from starlette.applications import Starlette
    from starlette.routing import Mount

    search_app = search_view.http_app(path="/mcp")
    code_app = code_view.http_app(path="/mcp")

    @contextlib.asynccontextmanager
    async def lifespan(app):
        async with contextlib.AsyncExitStack() as stack:
            for sub in (search_app, code_app):
                await stack.enter_async_context(sub.router.lifespan_context(sub))
            yield

    app = Starlette(routes=[Mount("/search", app=search_app), Mount("/code", app=code_app)], lifespan=lifespan)
    uvicorn.run(app, host="127.0.0.1", port=port, log_level="warning")
