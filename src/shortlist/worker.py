from collections.abc import Callable
from threading import Event, Thread

from shortlist.config import Settings
from shortlist.domain import (
    Candidate,
    ExclusionUnknown,
    Profile,
    Research,
    Source,
    Unknown,
    exclusion_id,
    new_id,
)
from shortlist.fetch import FetchError, canonical_url, domain_of, fetch_page
from shortlist.journal import call_step
from shortlist.local_credentials import CredentialUnavailable, apply_local_credentials
from shortlist.market import (
    MarketResearch,
    competitor_query,
    market_candidates,
    read_campaign_plan,
)
from shortlist.progress import ProgressUpdate, step_label
from shortlist.providers import (
    Gemma,
    ModelOutputError,
    ProviderError,
    Search,
    SearchProvider,
    SellerDraft,
    company_name_matches,
    queries_for,
)
from shortlist.relevance import candidate_issue, company_page_issue
from shortlist.selection import prioritize, prioritize_pages
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

    def prompt_inputs() -> dict:
        # Compact and Ollama requests differ from the hosted shape; journal them as distinct inputs.
        return model.runtime.journal() if isinstance(model, Gemma) else {}

    def call(kind: str, provider: str, operation: str, function, inputs: dict, decode):
        phase = ("market" if operation == "market:search" else "campaigns" if operation == "market:campaigns"
                 else "seller" if operation.startswith("seller:") else "discovery" if kind == "search" else "research")
        label = step_label(kind, operation)
        dispatched = False

        def traced():
            nonlocal dispatched
            dispatched = True
            store.event(run_id, fence, ProgressUpdate(phase=phase, label=label, state="started"))
            return function()

        try:
            result = call_step(store, run_id, fence, settings.global_search_cap, kind=kind, provider=provider,
                               operation=operation, function=traced, inputs=inputs, decode=decode)
        except (ProviderError, FetchError, BudgetExceeded) as exc:
            store.event(run_id, fence, ProgressUpdate(phase=phase, label=label, detail=str(exc)[:400], state="failed"))
            raise
        store.event(run_id, fence, ProgressUpdate(phase=phase, label=label,
                                                  state="succeeded" if dispatched else "reused"))
        return result

    def page(url: str, domain: str, operation: str, *, seller: bool = False):
        url = canonical_url(url)
        source = store.cached_source(url, domain, settings.source_cache_hours, run_id=run_id, operation=operation)
        if source is not None:
            checkpoint.setdefault("source_reuse", {})[operation] = {
                "source_id": source.id, "retrieved_at": source.retrieved_at.isoformat(),
                "max_age_hours": settings.source_cache_hours}
            store.event(run_id, fence, ProgressUpdate(phase="seller" if seller else "research",
                label="Reusing a fresh saved page from " + domain, state="reused"))
            return source
        source = call("fetch", "https", operation,
                      lambda: fetch(url) if seller else fetch(url, expected_domain=domain),
                      {"url": url} if seller else {"url": url, "expected_domain": domain}, Source.model_validate)
        if source.company_domain != domain:
            raise FetchError("Fetched source changed company identity")
        store.cache_source(run_id, fence, url, source)
        return source

    def reject_candidate(candidate, reason, stage):
        checkpoint.setdefault("candidate_failures", {})[candidate.domain] = {"url": candidate.url, "reason": reason}
        store.event(run_id, fence, ProgressUpdate(phase="discovery", label="Skipped non-company page: " + candidate.domain,
                                                detail=reason, state="failed"))
        store.checkpoint(run_id, fence, stage, checkpoint)

    def explore_market(draft):
        if "market" in checkpoint:
            return
        store.checkpoint(run_id, fence, "campaigns" if "market_candidates" in checkpoint else "market", checkpoint)
        if "market_candidates" not in checkpoint:
            query = competitor_query(draft.offer, checkpoint["seller_url"])

            def decode_market(values):
                try:
                    return market_candidates(values, checkpoint["seller_url"])
                except ValueError as exc:
                    raise ProviderError("Competitor search returned invalid website identities") from exc
            try:
                candidates = call("search", search.name, "market:search",
                                  lambda: decode_market(search.search(query, checkpoint["seller_url"])),
                                  {"query": query, "seller_url": checkpoint["seller_url"], "market_policy": 1}, decode_market)
                checkpoint["market_candidates"] = [c.model_dump(mode="json") for c in candidates]
            except (ProviderError, BudgetExceeded):
                checkpoint["market_candidates"] = []
                checkpoint["market_search_issue"] = "Competitor search could not finish. You can still confirm your target."
            store.checkpoint(run_id, fence, "market", checkpoint)
        candidates = [Candidate.model_validate(c) for c in checkpoint["market_candidates"]]
        if "market_plan" not in checkpoint and "market_plan_issue" not in checkpoint:
            store.checkpoint(run_id, fence, "campaigns", checkpoint)
            try:
                plan = call("model", model.name, "market:campaigns", lambda: model.market(draft, candidates),
                            {"draft": draft.model_dump(mode="json"), "candidates": checkpoint["market_candidates"],
                             "model": settings.gemma_model, "endpoint": settings.gemma_base_url, "campaign_policy": 2,
                             **prompt_inputs()},
                            read_campaign_plan)
                checkpoint["market_plan"] = plan.model_dump(mode="json")
            except (ProviderError, BudgetExceeded) as exc:
                checkpoint["market_plan_issue"] = "Campaign suggestions are unavailable. Define your target below to continue."
                if isinstance(exc, ModelOutputError):
                    checkpoint["market_model_output"] = exc.diagnostic()
            store.checkpoint(run_id, fence, "campaigns", checkpoint)
        plan = read_campaign_plan(checkpoint.get("market_plan", {"campaigns": []}))
        campaigns = plan.campaigns
        issues = [checkpoint[key] for key in ("market_search_issue", "market_plan_issue") if key in checkpoint]
        issues.extend(plan.issues)
        if not candidates and "market_search_issue" not in checkpoint:
            issues.append("No potential competitors were found in this search.")
        if not campaigns and "market_plan_issue" not in checkpoint:
            issues.append("No distinct campaigns were proposed. Define your target below.")
        checkpoint["market"] = MarketResearch(competitors=tuple(candidates), campaigns=campaigns,
            status="partial" if issues else "saved", issues=tuple(issues)).model_dump(mode="json")
        store.checkpoint(run_id, fence, "campaigns", checkpoint)

    try:
        store.event(run_id, fence, ProgressUpdate(phase={"seller": "seller", "identity": "seller", "market": "market", "campaigns": "campaigns"}.get(run["stage"], "discovery"),
                                                   label="Research worker picked up your saved run", state="succeeded"))
        if run["stage"] == "identity":
            error = None
            def decode_lookup(values):
                try:
                    matches = [Candidate.model_validate(value) for value in values]
                    for match in matches:
                        if canonical_url(match.url) != match.url or domain_of(match.url) != match.domain:
                            raise ValueError("Website identity mismatch")
                    return matches
                except ValueError as exc:
                    raise ProviderError("Website lookup returned an invalid public website") from exc
            try:
                query = '"' + checkpoint["company_name"] + '" official company website'
                matches = call("search", search.name, "seller:identity", lambda: decode_lookup(search.search(query, None)),
                               {"query": query, "company_name": checkpoint["company_name"]},
                               decode_lookup)
                matches = [match for match in matches if company_name_matches(match, checkpoint["company_name"])]
                checkpoint["website_matches"] = [match.model_dump(mode="json") for match in matches[:3]]
                if not matches:
                    error = "No website matches were found. Enter your company's website below to continue."
            except (ProviderError, BudgetExceeded, Conflict) as exc:
                checkpoint["website_matches"] = []
                checkpoint["website_lookup_error"] = str(exc)
                error = "We couldn't finish the website lookup. Enter your company's website below to continue."
            store.event(run_id, fence, ProgressUpdate(phase="seller", label="Choose the website for your company", state="waiting"))
            store.checkpoint(run_id, fence, "website", checkpoint, "awaiting_confirmation", error)
            return True
        if run["stage"] in ("seller", "market", "campaigns"):
            error = None
            try:
                if "seller_source" not in checkpoint:
                    source = page(checkpoint["seller_url"], domain_of(checkpoint["seller_url"]), "seller:fetch", seller=True)
                    checkpoint["seller_source"] = source.model_dump(mode="json")
                    store.checkpoint(run_id, fence, "seller", checkpoint)
                source = Source.model_validate(checkpoint["seller_source"])
                if "draft" in checkpoint:
                    draft = SellerDraft.model_validate(checkpoint["draft"])
                else:
                    seller_inputs = {"source": source.model_dump(mode="json"), "model": settings.gemma_model,
                                     "endpoint": settings.gemma_base_url, **prompt_inputs()}
                    protocol = checkpoint.get("seller_output_protocol", 1)
                    if protocol != 1:
                        seller_inputs["output_protocol"] = protocol
                    draft = call("model", model.name, "seller:model",
                                 lambda: model.seller(source, output_protocol=protocol) if isinstance(model, Gemma)
                                 else model.seller(source), seller_inputs, SellerDraft.model_validate)
                    checkpoint["draft"] = draft.model_dump(mode="json")
                    store.checkpoint(run_id, fence, "seller", checkpoint)
                if checkpoint.get("experience_version", 1) == 2:
                    explore_market(draft)
            except (FetchError, ProviderError) as exc:
                if isinstance(exc, ModelOutputError):
                    checkpoint["seller_model_output"] = exc.diagnostic()
                error = str(exc) + ". Enter and confirm your offer and target manually to continue."
            store.event(run_id, fence, ProgressUpdate(phase="confirmation", label="Ready for your offer and target confirmation",
                                                       state="waiting"))
            store.checkpoint(run_id, fence, "confirmation", checkpoint, "awaiting_confirmation", error)
            return True
        profile = Profile.model_validate(run["profile"])
        if "candidates" not in checkpoint:
            discovered = checkpoint.get("discovered", [])
            completed_queries = checkpoint.get("completed_queries", [])
            for index, query in enumerate(queries_for(profile, checkpoint.get("discovery_terms"))):
                if checkpoint.get("use_saved_discovery") or index in completed_queries or str(index) in checkpoint.get("discovery_failures", {}):
                    continue
                try:
                    candidates = call("search", search.name, f"search:{index}", lambda q=query: search.search(q, profile.seller_url),
                                      {"query": query, "seller_url": profile.seller_url},
                                      lambda results: [Candidate.model_validate(c) for c in results])
                except (ProviderError, BudgetExceeded) as exc:
                    checkpoint.setdefault("discovery_failures", {})[str(index)] = str(exc)
                    store.checkpoint(run_id, fence, "discovery", checkpoint)
                    continue
                discovered.extend(c.model_dump(mode="json") for c in candidates)
                completed_queries.append(index)
                checkpoint.update(discovered=discovered, completed_queries=completed_queries)
                store.checkpoint(run_id, fence, "discovery", checkpoint)
            unique = {c["domain"]: c for c in reversed(discovered)}
            candidates, selection = prioritize(profile, [Candidate.model_validate(c) for c in reversed(list(unique.values()))][:12])
            checkpoint["candidates"] = [c.model_dump(mode="json") for c in candidates]
            checkpoint["selection"] = [item.model_dump(mode="json") for item in selection]
            store.checkpoint(run_id, fence, "research", checkpoint)
            store.event(run_id, fence, ProgressUpdate(phase="discovery",
                label=f"Saved {len(checkpoint['candidates'])} unique company candidates", state="succeeded"))
            store.event(run_id, fence, ProgressUpdate(phase="discovery", label="Prioritized candidates against your target",
                detail="Target wording first, then public event clues. Search clues still need verification.", state="succeeded"))
        if checkpoint.get("selection_policy") in (2, 3) and not checkpoint.get("page_selection_complete"):
            pool = [Candidate.model_validate(c) for c in checkpoint["candidates"][:6]]
            store.checkpoint(run_id, fence, "selection", checkpoint)
            for candidate in pool:
                saved_sources = checkpoint.setdefault("sources", {})
                if candidate.domain in checkpoint.get("candidate_failures", {}):
                    continue
                if issue := candidate_issue(candidate):
                    reject_candidate(candidate, issue, "selection")
                    continue
                if candidate.domain in saved_sources:
                    primary = Source.model_validate(saved_sources[candidate.domain][0])
                    if issue := company_page_issue(primary.url, primary.title):
                        reject_candidate(candidate, issue, "selection")
                    continue
                try:
                    source = page(candidate.url, candidate.domain, f"fetch:{candidate.domain}")
                    saved_sources[candidate.domain] = [source.model_dump(mode="json")]
                    if issue := company_page_issue(source.url, source.title):
                        reject_candidate(candidate, issue, "selection")
                except FetchError as exc:
                    checkpoint.setdefault("candidate_failures", {})[candidate.domain] = {"url": candidate.url, "reason": str(exc)}
                store.checkpoint(run_id, fence, "selection", checkpoint)
            if checkpoint.get("selection_policy") == 3:
                for candidate in pool:
                    if candidate.domain in checkpoint.get("candidate_failures", {}):
                        continue
                    pages = checkpoint.get("sources", {}).get(candidate.domain, [])
                    if not pages:
                        continue
                    primary = Source.model_validate(pages[0])
                    if not primary.activity_links:
                        continue
                    link = primary.activity_links[0]
                    completed = checkpoint.setdefault("completed_activity", {})
                    failures = checkpoint.setdefault("activity_failures", {})
                    if candidate.domain in completed or candidate.domain in failures:
                        continue
                    try:
                        if domain_of(link) != candidate.domain:
                            raise FetchError("Activity link changed company identity")
                        activity = page(link, candidate.domain, f"fetch:{candidate.domain}:activity")
                        if activity.url not in {s["url"] for s in pages}:
                            pages.append(activity.model_dump(mode="json"))
                        completed[candidate.domain] = link
                    except FetchError as exc:
                        failures[candidate.domain] = {"url": link, "reason": str(exc)}
                    store.checkpoint(run_id, fence, "selection", checkpoint)
            selected_campaign = next((c for c in checkpoint.get("market", {}).get("campaigns", [])
                                      if c["name"] == checkpoint.get("campaign_name")), None)
            preferences = selected_campaign.get("signals_to_check", []) if selected_campaign else []
            eligible = [c for c in pool if c.domain not in checkpoint.get("candidate_failures", {})]
            ranked, explanations = prioritize_pages(profile, eligible,
                {domain: tuple(Source.model_validate(s) for s in pages) for domain, pages in checkpoint.get("sources", {}).items()},
                checkpoint.get("discovery_terms"), preferences)
            rejected = [c.model_dump(mode="json") for c in pool if c not in eligible]
            checkpoint["candidates"] = [c.model_dump(mode="json") for c in ranked] + rejected + checkpoint["candidates"][6:]
            checkpoint["selection"] = [s.model_dump(mode="json") for s in explanations] + checkpoint.get("selection", [])[6:]
            checkpoint["page_selection_complete"] = True
            store.event(run_id, fence, ProgressUpdate(phase="discovery", label="Selected research candidates from saved company pages",
                detail="Dated company statements are source claims, not buying intent. Missing dates receive no signal priority.", state="succeeded"))
            store.checkpoint(run_id, fence, "research", checkpoint)
        researched = {r["research"]["domain"] for r in store.get_run(run_id)["records"]}
        for data in checkpoint["candidates"][:6]:
            candidate = Candidate.model_validate(data)
            if candidate.domain in researched or candidate.domain in checkpoint.get("candidate_failures", {}):
                continue
            if len(store.get_run(run_id)["records"]) >= checkpoint.get("company_limit", 3):
                break
            if issue := candidate_issue(candidate):
                reject_candidate(candidate, issue, "research")
                continue
            billable = False
            saved_sources = checkpoint.setdefault("sources", {})
            try:
                if candidate.domain not in saved_sources:
                    source = page(candidate.url, candidate.domain, f"fetch:{candidate.domain}")
                    saved_sources[candidate.domain] = [source.model_dump(mode="json")]
                    store.checkpoint(run_id, fence, "research", checkpoint)
                sources = tuple(Source.model_validate(s) for s in saved_sources[candidate.domain])
                if issue := company_page_issue(sources[0].url, sources[0].title):
                    reject_candidate(candidate, issue, "research")
                    continue
                # Initial-page links define the entire follow-up frontier. Never recurse.
                completed_pages = checkpoint.setdefault("completed_pages", {}).setdefault(candidate.domain, [])
                failures = checkpoint.setdefault("page_failures", {}).setdefault(candidate.domain, {})
                for index, link in enumerate(sources[0].research_links):
                    if link in completed_pages or link in failures or link in {s.url for s in sources}:
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
                                "model": settings.gemma_model, "endpoint": settings.gemma_base_url, "exclusion_policy": 1,
                                **prompt_inputs()}
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
                billable = True
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
                                 {"profile": profile.model_dump(mode="json"),
                                  "research": record.model_dump(mode="json", exclude={
                                      key for key in ("company_facts", "people") if not getattr(record, key)}),
                                  "model": settings.gemma_model, "endpoint": settings.gemma_base_url,
                                  "verification_policy": 2, **prompt_inputs()}, decode_verification)
                    record = apply_verification(profile, record, audit)
                    checkpoint.setdefault("verification", {})[candidate.domain] = audit.model_dump(mode="json")
                except (ProviderError, BudgetExceeded) as exc:
                    billable = False
                    record = unavailable(profile, record, str(exc))
                    checkpoint.setdefault("verification", {})[candidate.domain] = {"error": str(exc)}
            store.save_record(run_id, fence, record, billable=billable)
            store.event(run_id, fence, ProgressUpdate(phase="research", label="Saved research for " + candidate.domain,
                                                       state="succeeded"))
            store.checkpoint(run_id, fence, "research", checkpoint)
        records = store.get_run(run_id)["records"]
        incomplete_pages = any(checkpoint.get("page_failures", {}).values()) or bool(checkpoint.get("activity_failures"))
        incomplete_discovery = bool(checkpoint.get("discovery_failures")) or bool(checkpoint.get("use_saved_discovery"))
        partial = (not records or incomplete_pages or incomplete_discovery
                   or any(r["research"]["status"] == "partial" for r in records))
        store.event(run_id, fence, ProgressUpdate(phase="review", label=f"Saved {len(records)} companies for your review",
                                                   state="waiting"))
        store.checkpoint(run_id, fence, "review", checkpoint, "partial" if partial else "ready",
                         ("No readable company evidence could be collected" if checkpoint.get("candidate_failures")
                          else "No candidate companies found") if not records else
                         "Some linked company pages could not be fetched; review the saved sources." if incomplete_pages else
                         "Discovery was incomplete; these records use the candidates that were saved." if incomplete_discovery else None)
    except (ProviderError, FetchError, BudgetExceeded, Conflict) as exc:
        # Lost lease cannot write; the replacement worker owns the current state.
        try:
            store.event(run_id, fence, ProgressUpdate(phase="seller" if run["stage"] == "seller" else "research",
                                                       label=str(exc)[:400], state="failed"))
            store.checkpoint(run_id, fence, run["stage"], checkpoint, "partial", str(exc))
        except Conflict:
            pass
    return True


def work(settings: Settings, once: bool = False, *, stopped: Event | None = None, started: Event | None = None):
    if settings.mode == "hosted":
        from shortlist.postgres import PostgresStore
        if not settings.worker_database_url.get_secret_value():
            raise ValueError("Hosted worker requires its separate database credential")
        store = PostgresStore(settings.worker_database_url, None, worker=True)
    else:
        store = Store(settings.db_path)
    worker_id = new_id()
    stopped = stopped if stopped is not None else Event()
    store.worker_heartbeat(worker_id)

    def heartbeat():
        while not stopped.wait(5):
            store.worker_heartbeat(worker_id)

    thread = Thread(target=heartbeat, name="shortlist-worker-heartbeat", daemon=True)
    thread.start()
    if started is not None:
        started.set()
    try:
        while not stopped.is_set():
            for run_id in store.pending_runs():
                if stopped.is_set():
                    break
                try:
                    configuration = apply_local_credentials(settings)
                except CredentialUnavailable:
                    if once:
                        raise
                    continue  # Keep queued work and setup access; dispatch no provider.
                execute_run(store.for_run(run_id) if settings.mode == "hosted" else store,
                            configuration, run_id)
            if once:
                return
            stopped.wait(2)
    finally:
        stopped.set()
        thread.join(timeout=5)
        store.remove_worker(worker_id)
