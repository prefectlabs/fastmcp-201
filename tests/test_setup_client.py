"""setup_client.py builds a valid Claude Code .mcp.json: one entry, a token that verifies."""

import json

import jwt

import setup_client
from weather.keys import AUDIENCE, ISSUER, ensure_keypair


def test_build_has_one_entry_with_the_token():
    servers = setup_client.build(token="TOKEN")
    assert list(servers) == ["weather"]
    assert servers["weather"]["url"] == "http://127.0.0.1:8201/mcp"
    assert servers["weather"]["headers"]["Authorization"] == "Bearer TOKEN"
    assert json.dumps({"mcpServers": servers})  # serialisable


def test_minted_tokens_carry_the_scopes():
    from lab import mint

    claims = jwt.decode(mint("weather:read", "weather:write", ttl=60), ensure_keypair().public_key, algorithms=["RS256"], audience=AUDIENCE, issuer=ISSUER)
    assert claims["scope"] == "weather:read weather:write"
