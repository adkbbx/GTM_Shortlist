import time
from collections.abc import Callable

from shortlist.config import Settings
from shortlist.domain import Candidate, Profile, Research, Source, Unknown
from shortlist.fetch import FetchError, fetch_page
from shortlist.providers import (
    Gemma,
    ModelOutputError,
    ProviderError,
    Search,
    SearchProvider,
    queries_for,
)
from shortlist.store import BudgetExceeded, Conflict, Store


def execute_run(store: Store, settings: Settings, run_id: str, *, search: Search | None = None,
                model: Gemma | None = None, fetch: Callable[..., Source] = fetch_page) -> bool:
    fence = store.claim(run_id)
    if fence is None:
        return False
    run = store.get_run(run_id)
    checkpoint = run["checkpoint"]
    search = search or SearchProvider(settings)
    model = model or Gemma(settings)

    def call(kind: str, provider: str, operation: str, function):
        attempt = store.reserve(run_id, fence, provider, kind, operation, settings.global_search_cap)
        try:
            result = function()
        except (ProviderError, FetchError):
            store.outcome(attempt, "failed")
            raise
        store.outcome(attempt, "succeeded")
        return result

    try:
        if run["stage"] == "seller":
            error = None
            try:
                if "seller_source" not in checkpoint:
                    source = call("fetch", "https", "seller:fetch", lambda: fetch(checkpoint["seller_url"]))
                    checkpoint["seller_source"] = source.model_dump(mode="json")
                    store.checkpoint(run_id, fence, "seller", checkpoint)
                source = Source.model_validate(checkpoint["seller_source"])
                draft = call("model", model.name, "seller:model", lambda: model.seller(source))
                checkpoint["draft"] = draft.model_dump(mode="json")
            except (FetchError, ProviderError) as exc:
                if isinstance(exc, ModelOutputError):
                    checkpoint["seller_model_output"] = exc.diagnostic()
                error = str(exc) + ". Enter and confirm your offer and target manually to continue."
            store.checkpoint(run_id, fence, "confirmation", checkpoint, "awaiting_confirmation", error)
            return True
        profile = Profile.model_validate(run["profile"])
        if "candidates" not in checkpoint:
            discovered = checkpoint.get("discovered", [])
            completed_queries = checkpoint.get("completed_queries", [])
            for index, query in enumerate(queries_for(profile)):
                if index in completed_queries:
                    continue
                candidates = call("search", search.name, f"search:{index}", lambda q=query: search.search(q, profile.seller_url))
                discovered.extend(c.model_dump(mode="json") for c in candidates)
                completed_queries.append(index)
                checkpoint.update(discovered=discovered, completed_queries=completed_queries)
                store.checkpoint(run_id, fence, "discovery", checkpoint)
            unique = {c["domain"]: c for c in reversed(discovered)}
            checkpoint["candidates"] = list(reversed(list(unique.values())))[:12]
            store.checkpoint(run_id, fence, "research", checkpoint)
        researched = {r["research"]["domain"] for r in store.get_run(run_id)["records"]}
        for data in checkpoint["candidates"][:6]:
            candidate = Candidate.model_validate(data)
            if candidate.domain in researched:
                continue
            if len(store.get_run(run_id)["records"]) >= 3:
                break
            saved_sources = checkpoint.setdefault("sources", {})
            try:
                if candidate.domain not in saved_sources:
                    source = call("fetch", "https", f"fetch:{candidate.domain}",
                                  lambda c=candidate: fetch(c.url, expected_domain=c.domain))
                    saved_sources[candidate.domain] = [source.model_dump(mode="json")]
                    store.checkpoint(run_id, fence, "research", checkpoint)
                sources = tuple(Source.model_validate(s) for s in saved_sources[candidate.domain])
                diagnostics = checkpoint.setdefault("model_outputs", {})
                previous = diagnostics.get(candidate.domain)
                if previous is None:
                    try:
                        record = call("model", model.name, f"model:{candidate.domain}",
                                      lambda c=candidate, s=sources: model.research(profile, c, s))
                    except ModelOutputError as exc:
                        previous = exc.diagnostic()
                        diagnostics[candidate.domain] = previous
                        # Save invalid output before another dispatch; a resumed worker can
                        # repair it without paying for the original request again.
                        store.checkpoint(run_id, fence, "research", checkpoint)
                if previous is not None:
                    try:
                        record = call("model", model.name, f"repair:{candidate.domain}",
                                      lambda c=candidate, s=sources, p=previous: model.research(profile, c, s, repair=p))
                    except ModelOutputError as exc:
                        diagnostics[candidate.domain]["repair_failure"] = exc.diagnostic()
                        store.checkpoint(run_id, fence, "research", checkpoint)
                        raise
            except (ProviderError, FetchError) as exc:
                sources = tuple(Source.model_validate(s) for s in saved_sources.get(candidate.domain, []))
                record = Research(domain=candidate.domain, name=candidate.name, profile_id=profile.id,
                                  findings=tuple(Unknown(criterion_id=c.id, reason=str(exc)) for c in profile.criteria),
                                  sources=sources, qualification="needs_verification", status="partial", unknowns=(str(exc),))
            store.save_record(run_id, fence, record)
            store.checkpoint(run_id, fence, "research", checkpoint)
        records = store.get_run(run_id)["records"]
        partial = not records or any(r["research"]["status"] == "partial" for r in records)
        store.checkpoint(run_id, fence, "review", checkpoint, "partial" if partial else "ready",
                         "No candidate companies found" if not records else None)
    except (ProviderError, FetchError, BudgetExceeded, Conflict) as exc:
        # Lost lease cannot write; the replacement worker owns the current state.
        try:
            store.checkpoint(run_id, fence, run["stage"], checkpoint, "partial", str(exc))
        except Conflict:
            pass
    return True


def work(settings: Settings, once: bool = False):
    store = Store(settings.db_path)
    while True:
        pending = [r for r in store.list_runs() if r["status"] in ("queued", "running")]
        for run in reversed(pending):
            execute_run(store, settings, run["id"])
        if once:
            return
        time.sleep(2)
