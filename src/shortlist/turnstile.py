"""Cloudflare Turnstile: the bot check before a draft that spends a model call without an account."""
import httpx
from pydantic import SecretStr

VERIFY_URL = "https://challenges.cloudflare.com/turnstile/v0/siteverify"


def verify_turnstile(secret: SecretStr, token: str, address: str | None = None, *,
                     transport: httpx.BaseTransport | None = None) -> bool:
    """True only for an explicit success from Cloudflare. Errors, timeouts and odd replies all count as a failed check."""
    data = {"secret": secret.get_secret_value(), "response": token, **({"remoteip": address} if address else {})}
    try:
        with httpx.Client(timeout=5, transport=transport, follow_redirects=False) as client:
            response = client.post(VERIFY_URL, data=data)
        return response.status_code == 200 and response.json().get("success") is True
    except (httpx.HTTPError, ValueError, AttributeError):
        return False
