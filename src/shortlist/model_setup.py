"""Explicit metadata-only model discovery. Never requests inference or saves keys."""
import json
import re
import time

import httpx
from pydantic import BaseModel, Field

from shortlist.local_credentials import LocalModelConnection


class ModelSetupError(RuntimeError):
    pass


class LocalModels(BaseModel):
    models: list[str] = Field(max_length=200)


def available_models(connection: LocalModelConnection) -> LocalModels:
    token = connection.key.get_secret_value()
    headers = {"Authorization": "Bearer " + token} if token else {}
    payload = bytearray()
    deadline = time.monotonic() + 10
    try:
        with httpx.Client(timeout=5, follow_redirects=False, trust_env=False) as client, \
                client.stream("GET", connection.base_url + "/models", headers=headers) as response:
            if response.status_code in (401, 403):
                raise ModelSetupError("The server did not accept access. Check the API key and your provider account.")
            if response.status_code != 200:
                raise ModelSetupError("Model listing is unavailable. Check the server address or use advanced setup to enter the model ID.")
            for chunk in response.iter_bytes(chunk_size=65536):
                payload.extend(chunk)
                if len(payload) > 4 * 1024 * 1024 or time.monotonic() > deadline:
                    raise ModelSetupError("The model list was too large or too slow. Try again or use advanced setup.")
        result = json.loads(payload)
        if not isinstance(result, dict) or not isinstance(result.get("data"), list):
            raise ModelSetupError("The server did not return an OpenAI-compatible model list. Check its API address or use advanced setup.")
        ids = set()
        for entry in result["data"][:4096]:
            identity = entry.get("id") if isinstance(entry, dict) else None
            if isinstance(identity, str) and re.fullmatch(r"[A-Za-z0-9_./:@+-]{1,200}", identity) and not (token and token in identity):
                ids.add(identity)
        # Gemma-labelled entries come first, without guessing a model or
        # rejecting a server whose deployed Gemma model has a custom alias.
        return LocalModels(models=sorted(ids, key=lambda value: ("gemma" not in value.lower(), value))[:200])
    except (httpx.HTTPError, httpx.InvalidURL, ValueError):
        raise ModelSetupError("Could not read available models. Check that your model server is running and the address is correct.") from None
    finally:
        payload.clear()
