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
from shortlist.fetch import FetchError, canonical_url, domain_of, fetch_page
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
from shortlist.verification import (
    Verification,
    apply_verification,
    assessments,
    unavailable,
)


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

    def page(url: str, domain: str, operation: str, *, seller: bool = False):
        url = canonical_url(url)
        source = store.cached_source(url, domain, settings.source_cache_hours, run_id=run_id, operation=operation)
        if source is not None:
            checkpoint.setdefault("source_reuse", {})[operation] = {
                "source_id": source.id, "retrieved_at": source.retrieved_at.isoformat(),
                "max_age_hours": settings.source_cache_hours}
            return source
        source = call("fetch", "https", operation,
                      lambda: fetch(url) if seller else fetch(url, expected_domain=domain),
                      {"url": url} if seller else {"url": url, "expected_domain": domain}, Source.model_validate)
        if source.company_domain != domain:
            raise FetchError("Fetched source changed company identity")
        store.cache_source(run_id, fence, url, source)
        return source

    try:
        if run["stage"] == "seller":
            error = None
            try:
                if "seller_source" not in checkpoint:
                    source = page(checkpoint["seller_url"], domain_of(checkpoint["seller_url"]), "seller:fetch", seller=True)
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
            if candidate.domain in researched or candidate.domain in checkpoint.get("candidate_failures", {}):
                continue
            if len(store.get_run(run_id)["records"]) >= 3:
                break
            saved_sources = checkpoint.setdefault("sources", {})
            try:
                if candidate.domain not in saved_sources:
                    source = page(candidate.url, candidate.domain, f"fetch:{candidate.domain}")
                    saved_sources[candidate.domain] = [source.model_dump(mode="json")]
                    store.checkpoint(run_id, fence, "research", checkpoint)
                sources = tuple(Source.model_validate(s) for s in saved_sources[candidate.domain])
                # Initial-page links define the entire follow-up frontier. Never recurse.
                completed_pages = checkpoint.setdefault("completed_pages", {}).setdefault(candidate.domain, [])
                failures = checkpoint.setdefault("page_failures", {}).setdefault(candidate.domain, {})
                for index, link in enumerate(sources[0].research_links):
                    if link in completed_pages or link in failures:
                        continue
                    try:
                        if domain_of(link) != candidate.domain:
                            raise FetchError("Research link changed company identity")
                        additional = page(link, candidate.domain, f"fetch:{candidate.domain}:page:{index + 1}")
                        if additional.url not in {s.url for s in sources}:
                            sources = (*sources, additional)
                            saved_sources[candidate.domain] = [s.model_dump(mode="json") for s in sources]
                        completed_pages.append(link)
                    except FetchError as exc:
                        failures[link] = str(exc)
                    store.checkpoint(run_id, fence, "research", checkpoint)
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
                if isinstance(exc, FetchError) and not sources:
                    checkpoint.setdefault("candidate_failures", {})[candidate.domain] = {
                        "url": candidate.url, "reason": str(exc)}
                    store.checkpoint(run_id, fence, "research", checkpoint)
                    continue
                record = Research(domain=candidate.domain, name=candidate.name, profile_id=profile.id,
                                  findings=tuple(Unknown(criterion_id=c.id, reason=str(exc)) for c in profile.criteria),
                                  exclusion_findings=tuple(ExclusionUnknown(exclusion_id=exclusion_id(i), reason=str(exc))
                                                           for i in range(len(profile.exclusions))),
                                  sources=sources, qualification="needs_verification", status="partial", unknowns=(str(exc),))
            if assessments(profile, record):
                def decode_verification(payload, proposed=record):
                    audit = Verification.model_validate(payload)
                    apply_verification(profile, proposed, audit)
                    return audit

                try:
                    audit = call("model", model.name, f"verify:{candidate.domain}",
                                 lambda r=record: model.verify(profile, r),
                                 {"profile": profile.model_dump(mode="json"), "research": record.model_dump(mode="json"),
                                  "model": settings.gemma_model, "endpoint": settings.gemma_base_url,
                                  "verification_policy": 2}, decode_verification)
                    record = apply_verification(profile, record, audit)
                    checkpoint.setdefault("verification", {})[candidate.domain] = audit.model_dump(mode="json")
                except (ProviderError, BudgetExceeded) as exc:
                    record = unavailable(profile, record, str(exc))
                    checkpoint.setdefault("verification", {})[candidate.domain] = {"error": str(exc)}
            store.save_record(run_id, fence, record)
            store.checkpoint(run_id, fence, "research", checkpoint)
        records = store.get_run(run_id)["records"]
        incomplete_pages = any(checkpoint.get("page_failures", {}).values())
        partial = not records or incomplete_pages or any(r["research"]["status"] == "partial" for r in records)
        store.checkpoint(run_id, fence, "review", checkpoint, "partial" if partial else "ready",
                         ("No readable company evidence could be collected" if checkpoint.get("candidate_failures")
                          else "No candidate companies found") if not records else
                         "Some linked company pages could not be fetched; review the saved sources." if incomplete_pages else None)
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
