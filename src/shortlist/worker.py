import time
from collections.abc import Callable

from shortlist.config import Settings
from shortlist.domain import (
    Candidate,
    ExclusionUnknown,
    Profile,
    Research,
    Source,
    Unknown,
    exclusion_id,
)
from shortlist.fetch import FetchError, fetch_page
from shortlist.journal import call_step
from shortlist.providers import (
    Gemma,
    ModelOutputError,
    ProviderError,
    Search,
    SearchProvider,
    SellerDraft,
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

    def call(kind: str, provider: str, operation: str, function, inputs: dict, decode):
        return call_step(store, run_id, fence, settings.global_search_cap, kind=kind, provider=provider,
                         operation=operation, function=function, inputs=inputs, decode=decode)

    try:
        if run["stage"] == "seller":
            error = None
            try:
                if "seller_source" not in checkpoint:
                    source = call("fetch", "https", "seller:fetch", lambda: fetch(checkpoint["seller_url"]),
                                  {"url": checkpoint["seller_url"]}, Source.model_validate)
                    checkpoint["seller_source"] = source.model_dump(mode="json")
                    store.checkpoint(run_id, fence, "seller", checkpoint)
                source = Source.model_validate(checkpoint["seller_source"])
                draft = call("model", model.name, "seller:model", lambda: model.seller(source),
                             {"source": source.model_dump(mode="json"), "model": settings.gemma_model,
                              "endpoint": settings.gemma_base_url}, SellerDraft.model_validate)
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
                candidates = call("search", search.name, f"search:{index}", lambda q=query: search.search(q, profile.seller_url),
                                  {"query": query, "seller_url": profile.seller_url},
                                  lambda results: [Candidate.model_validate(c) for c in results])
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
                                  lambda c=candidate: fetch(c.url, expected_domain=c.domain),
                                  {"url": candidate.url, "expected_domain": candidate.domain}, Source.model_validate)
                    saved_sources[candidate.domain] = [source.model_dump(mode="json")]
                    store.checkpoint(run_id, fence, "research", checkpoint)
                sources = tuple(Source.model_validate(s) for s in saved_sources[candidate.domain])
                diagnostics = checkpoint.setdefault("model_outputs", {})
                previous = diagnostics.get(candidate.domain)
                model_inputs = {"profile": profile.model_dump(mode="json"), "candidate": candidate.model_dump(mode="json"),
                                "sources": [s.model_dump(mode="json") for s in sources],
                                "model": settings.gemma_model, "endpoint": settings.gemma_base_url, "exclusion_policy": 1}
                if previous is None:
                    try:
                        record = call("model", model.name, f"model:{candidate.domain}",
                                      lambda c=candidate, s=sources: model.research(profile, c, s),
                                      model_inputs, Research.model_validate)
                    except ModelOutputError as exc:
                        previous = exc.diagnostic()
                        diagnostics[candidate.domain] = previous
                        # Save invalid output before another dispatch; a resumed worker can
                        # repair it without paying for the original request again.
                        store.checkpoint(run_id, fence, "research", checkpoint)
                if previous is not None:
                    repair_input = {k: v for k, v in previous.items() if k != "repair_failure"}
                    try:
                        record = call("model", model.name, f"repair:{candidate.domain}",
                                      lambda c=candidate, s=sources, p=repair_input: model.research(profile, c, s, repair=p),
                                      {**model_inputs, "repair": repair_input},
                                      Research.model_validate)
                    except ModelOutputError as exc:
                        diagnostics[candidate.domain]["repair_failure"] = exc.diagnostic()
                        store.checkpoint(run_id, fence, "research", checkpoint)
                        raise
            except (ProviderError, FetchError) as exc:
                sources = tuple(Source.model_validate(s) for s in saved_sources.get(candidate.domain, []))
                record = Research(domain=candidate.domain, name=candidate.name, profile_id=profile.id,
                                  findings=tuple(Unknown(criterion_id=c.id, reason=str(exc)) for c in profile.criteria),
                                  exclusion_findings=tuple(ExclusionUnknown(exclusion_id=exclusion_id(i), reason=str(exc))
                                                           for i in range(len(profile.exclusions))),
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
        for run_id in store.pending_runs():
            execute_run(store, settings, run_id)
        if once:
            return
        time.sleep(2)
