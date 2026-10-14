import os
from pathlib import Path
from typing import Literal
from urllib.parse import urlsplit

from dotenv import load_dotenv
from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    SecretStr,
    field_validator,
    model_validator,
)


class Settings(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, hide_input_in_errors=True)
    db_path: Path = Path("data/shortlist.sqlite3")
    search_provider: str = "tavily"
    tavily_key: SecretStr = SecretStr("")
    serpapi_key: SecretStr = SecretStr("")
    gemma_key: SecretStr = SecretStr("")
    gemma_base_url: str = ""
    gemma_model: str = ""
    global_search_cap: int = Field(default=200, ge=1, le=250)
    source_cache_hours: int = Field(default=24, ge=0, le=168)
    mode: Literal["local", "hosted"] = "local"
    database_url: SecretStr = SecretStr("")
    worker_database_url: SecretStr = SecretStr("")
    supabase_url: str = ""
    supabase_publishable_key: str = ""
    app_url: str = ""
    booking_url: str = ""
    supabase_admin_key: SecretStr = SecretStr("")

    @field_validator("supabase_admin_key")
    @classmethod
    def server_admin_key(cls, value):
        key = value.get_secret_value()
        if key and not key.startswith("sb_secret_"):
            raise ValueError("Account closure requires a server-only Supabase secret key")
        return value

    @field_validator("booking_url")
    @classmethod
    def booking_destination(cls, value):
        if not value:
            return ""
        from shortlist.fetch import canonical_url
        return canonical_url(value)

    @model_validator(mode="after")
    def hosted_configuration(self):
        if self.mode == "hosted":
            for name, value in (("SUPABASE_URL", self.supabase_url), ("SHORTLIST_APP_URL", self.app_url)):
                try:
                    parsed = urlsplit(value)
                    valid = parsed.scheme == "https" and bool(parsed.hostname) and not parsed.username and not parsed.password and \
                        parsed.port in (None, 443) and parsed.path in ("", "/") and not parsed.query and not parsed.fragment
                except ValueError:
                    valid = False
                if not valid:
                    raise ValueError(f"{name} must be a plain HTTPS origin (https://hostname), without paths, credentials or Markdown")
            if not self.database_url.get_secret_value() or not self.supabase_publishable_key:
                raise ValueError("Hosted mode requires database and Supabase public configuration")
            if not self.supabase_publishable_key.startswith("sb_publishable_"):
                raise ValueError("Use a Supabase publishable key; secret/service-role keys must not reach the browser")
        return self

    @classmethod
    def load(cls):
        load_dotenv()
        settings = cls(
            db_path=os.getenv("SHORTLIST_DB", "data/shortlist.sqlite3"),
            search_provider=os.getenv("SHORTLIST_SEARCH_PROVIDER", "tavily"),
            tavily_key=os.getenv("TAVILY_API_KEY", ""),
            serpapi_key=os.getenv("SERPAPI_API_KEY", ""),
            gemma_key=os.getenv("GEMMA_API_KEY", ""),
            gemma_base_url=os.getenv("GEMMA_BASE_URL", ""),
            gemma_model=os.getenv("GEMMA_MODEL", ""),
            global_search_cap=os.getenv("SHORTLIST_GLOBAL_SEARCH_CAP", "200"),
            source_cache_hours=os.getenv("SHORTLIST_SOURCE_CACHE_HOURS", "24"),
            mode=os.getenv("SHORTLIST_MODE", "local"),
            database_url=os.getenv("SHORTLIST_DATABASE_URL", ""),
            worker_database_url=os.getenv("SHORTLIST_WORKER_DATABASE_URL", ""),
            supabase_url=os.getenv("SUPABASE_URL", ""),
            supabase_publishable_key=os.getenv("SUPABASE_PUBLISHABLE_KEY", ""),
            app_url=os.getenv("SHORTLIST_APP_URL", ""),
            booking_url=os.getenv("SHORTLIST_BOOKING_URL", ""),
            supabase_admin_key=os.getenv("SUPABASE_ADMIN_SECRET_KEY", ""),
        )
        return settings

    def readiness(self):
        return {
            "search": bool(self.tavily_key.get_secret_value()) if self.search_provider == "tavily"
            else bool(self.serpapi_key.get_secret_value()),
            "gemma": bool(self.gemma_base_url and self.gemma_model),
        }
