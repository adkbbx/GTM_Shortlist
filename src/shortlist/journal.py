"""Paid steps: reserve before dispatch, persist outcomes, replay without dispatch."""
import hashlib
import json
from collections.abc import Callable
from typing import Annotated, Literal, TypeVar

from pydantic import BaseModel, ConfigDict, Field, TypeAdapter, ValidationError

from shortlist.fetch import FetchError
from shortlist.providers import ModelOutputError, ProviderError
from shortlist.store import Conflict, Store

T = TypeVar("T")


class Diagnostic(BaseModel):
    model_config = ConfigDict(extra="forbid")
    content: str = Field(max_length=32000)
    issues: list[dict]


class ModelFailure(BaseModel):
    model_config = ConfigDict(extra="forbid")
    type: Literal["model_output"]
    diagnostic: Diagnostic


class TransportFailure(BaseModel):
    model_config = ConfigDict(extra="forbid")
    type: Literal["fetch", "provider"]
    message: str


FAILURE = TypeAdapter(Annotated[ModelFailure | TransportFailure, Field(discriminator="type")])


def call_step(store: Store, run_id: str, fence: int, global_cap: int, *, kind: str,
              provider: str, operation: str, inputs: dict, function: Callable[[], T],
              decode: Callable[[dict | list], T]) -> T:
    # Bump the version when an operation's interpretation changes. Input changes
    # during an in-flight run must fail loudly rather than replay a different value.
    digest = hashlib.sha256(json.dumps({"version": 1, "inputs": inputs}, sort_keys=True).encode()).hexdigest()
    saved = store.restore(run_id, fence, provider, kind, operation, digest)
    if saved is not None:
        payload = saved["payload"]
        if saved["state"] == "failed":
            try:
                failure = FAILURE.validate_python(payload)
            except ValidationError as exc:
                raise Conflict("Saved provider failure is corrupt; inspect or start a new run") from exc
            if isinstance(failure, ModelFailure):
                raise ModelOutputError(failure.diagnostic.content, failure.diagnostic.issues)
            error_type = FetchError if failure.type == "fetch" else ProviderError
            raise error_type(failure.message)
        try:
            return decode(payload)
        except (ValueError, TypeError, KeyError) as exc:
            raise Conflict("Saved provider result does not match this runtime; inspect or start a new run") from exc
    attempt = store.reserve(run_id, fence, provider, kind, operation, global_cap, request_hash=digest)
    try:
        result = function()
    except (ProviderError, FetchError) as exc:
        payload = {"type": "fetch" if isinstance(exc, FetchError) else "provider", "message": str(exc)}
        if isinstance(exc, ModelOutputError):
            payload = {"type": "model_output", "diagnostic": exc.diagnostic()}
        store.outcome(attempt, "failed", run_id=run_id, fence=fence, payload=payload)
        raise
    if isinstance(result, BaseModel):
        payload = result.model_dump(mode="json")
    else:
        payload = [item.model_dump(mode="json") for item in result]
    store.outcome(attempt, "succeeded", run_id=run_id, fence=fence, payload=payload)
    return result
