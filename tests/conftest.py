"""Shared test plumbing: impersonate a token holder for the in-memory client.

The in-memory client never goes through HTTP, so no JWT is verified. FastMCP
still runs authorization checks (only stdio skips them) and reads the caller's
token from the SDK's auth context variable, so tests set that directly.
"""

import contextlib

import pytest
from fastmcp.server.auth import AccessToken
from mcp.server.auth.middleware.auth_context import auth_context_var
from mcp.server.auth.middleware.bearer_auth import AuthenticatedUser


@contextlib.contextmanager
def as_caller(scopes: list[str], subject: str = "tester@example.gov"):
    """Pretend the current request carries a verified token with these scopes."""
    user = AuthenticatedUser(AccessToken(token="test-token", client_id="test", scopes=scopes, claims={"sub": subject}))
    token = auth_context_var.set(user)
    try:
        yield
    finally:
        auth_context_var.reset(token)


@pytest.fixture(scope="session", autouse=True)
def demo_keys():
    """server.py reads the public key at import; make sure the pair exists."""
    from weather.keys import ensure_keypair

    ensure_keypair()
