"""Operator settings for the agent. Keys come from the environment and never reach logs, results or the browser."""
import os
from typing import Literal

from dotenv import load_dotenv
from pydantic import BaseModel, ConfigDict, Field, SecretStr, field_validator

META_BASE_URL = "https://api.meta.ai/v1"
META_MODEL = "muse-spark-1.3"
BASETEN_BASE_URL = "https://inference.baseten.co/v1"
# The hackathon requires this exact Baseten model id; the unversioned id is a different deployment.
BASETEN_MODEL = "meta-models/muse-spark-open-1026"
UNVERSIONED_BASETEN_MODEL = "meta-models/muse-spark-open"

# Published Meta Model API prices used for telemetry estimates, in US dollars.
META_INPUT_USD_PER_M = 1.25
META_OUTPUT_USD_PER_M = 4.25
META_USD_PER_SEARCH = 2.50 / 1000


def https_base(value: str) -> str:
    value = value.strip().rstrip("/")
    if not value.startswith("https://") or any(ch.isspace() for ch in value):
        raise ValueError("Provider base URLs must be HTTPS")
    return value


class AgentSettings(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, hide_input_in_errors=True)
    meta_api_key: SecretStr = SecretStr("")
    meta_base_url: str = META_BASE_URL
    meta_model: str = Field(default=META_MODEL, min_length=1, max_length=200)
    # replay: resend the returned output items with each tool result (stateless).
    # previous: send only the tool results with previous_response_id.
    meta_continuation: Literal["replay", "previous"] = "replay"
    baseten_api_key: SecretStr = SecretStr("")
    baseten_base_url: str = BASETEN_BASE_URL
    baseten_model: str = Field(default=BASETEN_MODEL, min_length=1, max_length=200)
    baseten_json_mode: bool = True
    baseten_input_usd_per_m: float = Field(default=1.25, ge=0, le=1000)
    baseten_output_usd_per_m: float = Field(default=4.25, ge=0, le=1000)
    run_budget_usd: float = Field(default=1.00, gt=0, le=100)
    concurrency: int = Field(default=5, ge=1, le=10)
    # Ablation switch: off runs without the skeptic and labels the run as such.
    use_skeptic: bool = True

    @field_validator("meta_base_url", "baseten_base_url")
    @classmethod
    def https_only(cls, value):
        return https_base(value)

    @field_validator("baseten_model")
    @classmethod
    def versioned_skeptic(cls, value):
        if value.strip() == UNVERSIONED_BASETEN_MODEL:
            raise ValueError(f"Use {BASETEN_MODEL} for the skeptic; {UNVERSIONED_BASETEN_MODEL} is not the hackathon model")
        return value.strip()

    @classmethod
    def load(cls) -> "AgentSettings":
        load_dotenv()
        env = os.getenv
        return cls(
            meta_api_key=env("META_MODEL_API_KEY", ""),
            meta_base_url=env("META_MODEL_BASE_URL", META_BASE_URL) or META_BASE_URL,
            meta_model=env("META_MODEL", META_MODEL) or META_MODEL,
            meta_continuation=env("META_RESPONSES_CONTINUATION", "replay") or "replay",
            baseten_api_key=env("BASETEN_API_KEY", ""),
            baseten_base_url=env("BASETEN_BASE_URL", BASETEN_BASE_URL) or BASETEN_BASE_URL,
            baseten_model=env("BASETEN_MODEL", BASETEN_MODEL) or BASETEN_MODEL,
            baseten_json_mode=env("BASETEN_JSON_MODE", "on").strip().lower() != "off",
            baseten_input_usd_per_m=env("BASETEN_INPUT_USD_PER_M", "1.25") or "1.25",
            baseten_output_usd_per_m=env("BASETEN_OUTPUT_USD_PER_M", "4.25") or "4.25",
            run_budget_usd=env("AGENT_RUN_BUDGET_USD", "1.00") or "1.00",
            concurrency=env("AGENT_CONCURRENCY", "5") or "5",
            use_skeptic=env("AGENT_SKEPTIC", "on").strip().lower() != "off",
        )

    def readiness(self) -> dict[str, bool]:
        return {"investigator": bool(self.meta_api_key.get_secret_value()),
                "skeptic": bool(self.baseten_api_key.get_secret_value())}
