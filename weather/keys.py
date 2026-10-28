"""Demo JWT key pair and token settings shared by every step.

In production the identity provider holds the private key and publishes the
public half at a JWKS URL. Here ``mint_token.py`` plays the identity provider:
it generates an RSA pair under ``keys/`` once, signs tokens with the private
key, and the server only ever reads the public key.
"""

from pathlib import Path

from fastmcp.server.auth.providers.jwt import RSAKeyPair

REPO_ROOT = Path(__file__).resolve().parent.parent
KEYS_DIR = REPO_ROOT / "keys"
PRIVATE_KEY_PATH = KEYS_DIR / "private.pem"
PUBLIC_KEY_PATH = KEYS_DIR / "public.pem"

# These must match between the issuer (mint_token.py) and the verifier (server.py).
ISSUER = "https://idp.example.gov"
AUDIENCE = "weather-mcp"


def ensure_keypair() -> RSAKeyPair:
    """Return the demo key pair, generating and saving it on first use."""
    if PRIVATE_KEY_PATH.exists() and PUBLIC_KEY_PATH.exists():
        from pydantic import SecretStr

        return RSAKeyPair(
            private_key=SecretStr(PRIVATE_KEY_PATH.read_text()),
            public_key=PUBLIC_KEY_PATH.read_text(),
        )
    pair = RSAKeyPair.generate()
    KEYS_DIR.mkdir(exist_ok=True)
    PRIVATE_KEY_PATH.write_text(pair.private_key.get_secret_value())
    PUBLIC_KEY_PATH.write_text(pair.public_key)
    return pair


def load_public_key() -> str:
    """The verifier side: public key only. Fails loudly if no token was minted yet."""
    if not PUBLIC_KEY_PATH.exists():
        raise SystemExit(
            f"No public key at {PUBLIC_KEY_PATH}. Run steps/01_auth/mint_token.py first."
        )
    return PUBLIC_KEY_PATH.read_text()
