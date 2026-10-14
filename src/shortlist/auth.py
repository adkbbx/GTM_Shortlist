"""Verify bearer tokens at Supabase's user endpoint, never trust decoded claims."""
from datetime import UTC, datetime
from uuid import UUID

import httpx
from pydantic import BaseModel, ValidationError

from shortlist.config import Settings


class AuthenticationError(ValueError):
    pass


class AuthUnavailable(RuntimeError):
    pass


class VerifiedUser(BaseModel):
    id: UUID
    role: str
    email_confirmed_at: datetime | None = None
    is_anonymous: bool = False
    deleted_at: datetime | None = None
    banned_until: datetime | None = None


def verify_user(settings: Settings, token: str, *, transport=None) -> VerifiedUser:
    if not token or len(token) > 8192 or any(character.isspace() for character in token):
        raise AuthenticationError("Sign in to access your research")
    try:
        with (
            httpx.Client(timeout=5, follow_redirects=False, trust_env=False, transport=transport) as client,
            client.stream("GET", settings.supabase_url.rstrip("/") + "/auth/v1/user", headers={
                "apikey": settings.supabase_publishable_key, "Authorization": "Bearer " + token,
            }) as response,
        ):
                if response.status_code in (401, 403):
                    raise AuthenticationError("Your session has expired. Sign in again")
                if response.status_code != 200:
                    raise AuthUnavailable("Account verification is temporarily unavailable")
                content = bytearray()
                for chunk in response.iter_bytes():
                    content.extend(chunk)
                    if len(content) > 65536:
                        raise AuthUnavailable("Account verification is temporarily unavailable")
                user = VerifiedUser.model_validate_json(content)
    except (httpx.HTTPError, ValidationError) as exc:
        raise AuthUnavailable("Account verification is temporarily unavailable") from exc
    if user.role != "authenticated" or user.is_anonymous or user.deleted_at or not user.email_confirmed_at:
        raise AuthenticationError("Confirm your email before starting research")
    if user.banned_until and (user.banned_until.tzinfo is None or user.banned_until > datetime.now(UTC)):
        raise AuthenticationError("This account cannot access research")
    return user
