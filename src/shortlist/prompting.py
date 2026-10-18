"""Prompt profiles: compact requests for small or on-device models, full requests for hosted models.

Detection reads Ollama metadata only (/api/version, /api/show). It never requests inference.
"""
import json
import re
from dataclasses import dataclass
from typing import Literal
from urllib.parse import urlsplit

import httpx

from shortlist.config import Settings
from shortlist.domain import Source
from shortlist.selection import terms

LOOPBACK = frozenset({"localhost", "127.0.0.1", "::1"})
OLLAMA_PORT = 11434
SMALL_MODEL_BILLIONS = 10
COMPACT_CONTEXT = 8192
FULL_CONTEXT = 32768
# Measured about 3.25 characters per Gemma token for JSON page payloads; round down to stay inside the window.
CHARS_PER_TOKEN = 3
MINIMUM_SOURCE_CHARS = 1500
MENU_RUN = 8  # Consecutive lines of at most three words treated as a menu rather than page content.


@dataclass(frozen=True)
class Runtime:
    profile: Literal["compact", "full"]
    ollama: bool
    context: int | None = None  # Tokens the app sets per request; None when the server decides.
    thinking: bool = False

    def journal(self) -> dict:
        """Request-shape inputs. Empty for the original hosted shape, so its saved steps still replay."""
        if not self.ollama and self.profile == "full":
            return {}
        return {"prompt_profile": self.profile, "transport": "ollama" if self.ollama else "openai",
                "context": self.context}


def ollama_root(base_url: str) -> str:
    url = base_url.rstrip("/")
    return url.removesuffix("/v1")


def parameter_billions(size) -> float | None:
    match = re.fullmatch(r"\s*(\d+(?:\.\d+)?)\s*([BM])\s*", str(size or ""), re.IGNORECASE)
    if not match:
        return None
    value = float(match.group(1))
    return value / 1000 if match.group(2).upper() == "M" else value


def detect(settings: Settings) -> Runtime:
    """Choose the request shape from the model connection, not from local or hosted deployment."""
    parsed = urlsplit(settings.gemma_base_url)
    host = parsed.hostname or ""
    try:
        port = parsed.port
    except ValueError:
        port = None
    local = host in LOOPBACK or host.endswith(".localhost")
    ollama, billions, window, thinking = False, None, None, False
    if settings.mode != "hosted" and (local or port == OLLAMA_PORT):
        key = settings.gemma_key.get_secret_value()
        headers = {"Authorization": "Bearer " + key} if key else {}
        root = ollama_root(settings.gemma_base_url)
        try:
            with httpx.Client(timeout=3, trust_env=False, follow_redirects=False) as client:
                version = client.get(root + "/api/version", headers=headers)
                ollama = version.status_code == 200 and isinstance(version.json(), dict) and "version" in version.json()
                if ollama:
                    shown = client.post(root + "/api/show", headers=headers, json={"model": settings.gemma_model})
                    if shown.status_code == 200:
                        info = shown.json()
                        billions = parameter_billions(info.get("details", {}).get("parameter_size"))
                        window = next((value for name, value in info.get("model_info", {}).items()
                                       if name.endswith(".context_length") and isinstance(value, int)), None)
                        thinking = "thinking" in info.get("capabilities", [])
        except (httpx.HTTPError, ValueError, AttributeError, TypeError):
            ollama = False
    if settings.prompt_profile != "auto":
        profile = settings.prompt_profile
    elif settings.mode == "hosted":
        profile = "full"
    elif ollama:
        profile = "compact" if billions is None or billions < SMALL_MODEL_BILLIONS else "full"
    else:
        profile = "compact" if local else "full"
    context = None
    if ollama:
        context = COMPACT_CONTEXT if profile == "compact" else FULL_CONTEXT
        if window:
            context = min(context, window)
    return Runtime(profile=profile, ollama=ollama, context=context, thinking=thinking)


def source_budget(runtime: Runtime, fixed_chars: int, output_tokens: int, ceiling: int) -> int:
    """Characters of page text that fit beside the instructions and the reserved output."""
    if runtime.context is None:
        return ceiling
    return min(ceiling, (int(runtime.context * 0.9) - output_tokens) * CHARS_PER_TOKEN - fixed_chars)


def readable_spans(lines: list[str], menu_run: int = MENU_RUN) -> list[tuple[int, int]]:
    """Spans of consecutive lines left once long runs of one-to-three-word lines (language, region and navigation
    menus) are removed. On 18 October such menus filled most excerpts of NICE and Hitachi Energy, and the model quoted
    a region list instead of the partner programme. Shorter lists, such as a few features, are kept."""
    if menu_run == 0:
        return [(0, len(lines))]
    short = [len(line.split()) <= 3 for line in lines]
    spans, start, index = [], 0, 0
    while index < len(lines):
        if not short[index]:
            index += 1
            continue
        end = index
        while end < len(lines) and short[end]:
            end += 1
        if end - index >= menu_run:
            if start < index:
                spans.append((start, index))
            start = end
        index = end
    if start < len(lines):
        spans.append((start, len(lines)))
    return spans


def excerpts(sources: tuple[Source, ...], focus: str, budget: int, *, window: int = 400,
             menu_run: int = MENU_RUN) -> list[dict]:
    """Runs of consecutive page lines ranked by focus terms, returned in page order.

    Each run is verbatim page text, so a passage quoted from it passes the same grounding
    check against the saved page as a passage quoted from the whole page. Runs never cross a removed menu.
    Set menu_run=0 to keep menu lines for saved-evidence comparisons.
    """
    wanted = terms(focus)
    chunks = []
    for index, source in enumerate(sources):
        lines = source.text.splitlines()
        spans = readable_spans(lines, menu_run) or [(0, len(lines))]  # A page that is all menu is sent as it is.
        for first, last in spans:
            start = first
            while start < last:
                end, size = start, 0
                while end < last and (size < window or end == start):
                    size += len(lines[end]) + 1
                    end += 1
                text = "\n".join(lines[start:end])
                # The opening of the first page usually names the company and its offer.
                chunks.append((index == 0 and start == spans[0][0], len(wanted & terms(text)), -index, -start, index,
                               start, text))
                start = end
    chosen, used = {}, 0
    for opening, score, _, _, index, start, text in sorted(chunks, reverse=True):
        if not opening and not score:
            break
        cost = len(text) + (3 if index in chosen else 0)
        if used + cost > budget:
            continue
        chosen.setdefault(index, []).append((start, text))
        used += cost
    return [{"id": source.id, "url": source.url, "title": source.title,
             "text": "\n…\n".join(text for _, text in sorted(chosen[index]))}
            for index, source in enumerate(sources) if index in chosen]


def pinned(schema: dict, **choices: list[str]) -> dict:
    """A copy of a Pydantic JSON schema whose identifier fields accept only this run's values."""
    schema = json.loads(json.dumps(schema))

    def visit(node):
        if isinstance(node, dict):
            properties = node.get("properties", {})
            for name, values in choices.items():
                if values and isinstance(properties.get(name), dict):
                    properties[name] = {"type": "string", "enum": list(values)}
            for value in node.values():
                visit(value)
        elif isinstance(node, list):
            for value in node:
                visit(value)

    visit(schema)
    return schema
