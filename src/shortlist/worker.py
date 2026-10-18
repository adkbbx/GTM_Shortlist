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
    utcnow,
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
from shortlist.relevance import (
    CompanyPageError,
    candidate_issue,
    primary_source_issue,
    record_issue,
    research_entry,
)
from shortlist.sample import SAMPLE_PROVIDER, sample_providers
from shortlist.selection import prioritize, prioritize_pages
from shortlist.store import RUN_CAPS, BudgetExceeded, Conflict, Store
from shortlist.verification import (
    Verification,
    apply_verification,
    assessments,
    narrowed,
    unavailable,
    unjudged,
)

# Fewer unique companies than one selection pool after the planned discovery searches: try one more query.
LOW_YIELD = 6


def execute_run(store: Store, settings: Settings, run_id: str, *, search: Search | None = None,
                model: Gemma | None = None, fetch: Callable[..., Source] = fetch_page, sample_pace: float = 1.0) -> bool:
    fence = store.claim(run_id)
    if fence is None:
        return False
    run = store.get_run(run_id)
    checkpoint = run["checkpoint"]
    if checkpoint.get("sample"):
        # Sample runs never reach a provider: invented pages, results and assessments. Journal inputs stay stable
        # even if the person configures a real model while the sample is running.
        search, model, fetch = sample_providers(sample_pace)
        settings = settings.model_copy(update={"gemma_model": SAMPLE_PROVIDER, "gemma_base_url": ""})
    require_identity = checkpoint.get("company_identity_policy", 0) >= 1
    discovery_policy = checkpoint.get("discovery_policy", 1)

    def entry(candidate: Candidate) -> str:
        # Policy 2 starts at a company's own entry page instead of fetching a page the identity check would refuse.
        return research_entry(candidate.url, candidate.name) if discovery_policy >= 2 else candidate.url

    def room(kind: str, needed: int) -> bool:
        used = sum(attempt["kind"] == kind for attempt in store.get_run(run_id)["attempts"])
        return used + needed <= RUN_CAPS[kind]

    def room_for(kind: str, *operations: str) -> bool:
        # Restoring a journaled call needs no remaining provider allowance.
        with store.connection() as db:
            dispatched = {row["operation_key"] for row in db.execute(
                "SELECT operation_key FROM attempts WHERE run_id=? AND kind=?", (run_id, kind))}
        return room(kind, sum(operation not in dispatched for operation in operations))

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
        except (ProviderError, FetchError, BudgetExceeded, CompanyPageError) as exc:
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
        market_policy = checkpoint.get("market_policy", 1)
        if "market_candidates" not in checkpoint:
            query = competitor_query(draft.offer, checkpoint["seller_url"], policy=market_policy)

            def decode_market(values):
                try:
                    return market_candidates(values, checkpoint["seller_url"],
                                             offer=draft.offer, strict=market_policy >= 2)
                except ValueError as exc:
                    raise ProviderError("Competitor search returned invalid website identities") from exc
            try:
                candidates = call("search", search.name, "market:search",
                                  lambda: decode_market(search.search(query, checkpoint["seller_url"])),
                                  {"query": query, "seller_url": checkpoint["seller_url"], "market_policy": market_policy}, decode_market)
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
                             "model": settings.gemma_model, "endpoint": settings.gemma_base_url, "campaign_policy": 3 if market_policy >= 2 else 2,
                             **prompt_inputs()},
                            read_campaign_plan)
                checkpoint["market_plan"] = plan.model_dump(mode="json")
            except (ProviderError, BudgetExceeded) as exc:
                checkpoint["market_plan_issue"] = "Campaign suggestions are unavailable. Define your target below to continue."
                if isinstance(exc, ModelOutputError):
                    checkpoint["market_model_output"] = exc.diagnostic()
            store.checkpoint(run_id, fence, "campaigns", checkpoint)
        plan = read_campaign_plan(checkpoint.get("market_plan", {"campaigns": []}), distinct_targets=market_policy >= 2)
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
            # Policy 2 sets aside companies already saved in this workspace's other shortlists for the same seller:
            # repeat runs kept paying to research the same companies. Saved once so a resumed run decides the same way.
            if discovery_policy >= 2 and "earlier_shortlists" not in checkpoint:
                checkpoint["earlier_shortlists"] = sorted(store.researched_elsewhere(run_id, profile.seller_url))
                store.checkpoint(run_id, fence, "discovery", checkpoint)
            earlier = set(checkpoint.get("earlier_shortlists", []))
            for index, query in enumerate(queries_for(profile, checkpoint.get("discovery_terms"), policy=discovery_policy)):
                if checkpoint.get("use_saved_discovery") or index in completed_queries or str(index) in checkpoint.get("discovery_failures", {}):
                    continue
                # The extra query is spent only when the first two left too few companies, and never past the run's cap.
                if index >= 2 and (len({c["domain"] for c in discovered} - earlier) >= LOW_YIELD or not room("search", 1)):
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
            set_aside = sorted(domain for domain in unique if domain in earlier)
            candidates, selection = prioritize(profile, [Candidate.model_validate(c) for c in reversed(list(unique.values()))
                                                         if c["domain"] not in earlier][:12])
            checkpoint["candidates"] = [c.model_dump(mode="json") for c in candidates]
            checkpoint["selection"] = [item.model_dump(mode="json") for item in selection]
            if set_aside:
                checkpoint["previously_researched"] = set_aside
            store.checkpoint(run_id, fence, "research", checkpoint)
            if set_aside:
                store.event(run_id, fence, ProgressUpdate(phase="discovery", state="reused",
                    label=f"Set aside {len(set_aside)} {'company' if len(set_aside) == 1 else 'companies'} already in your earlier shortlists for this offer",
                    detail=", ".join(set_aside[:6])))
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
                    if issue := primary_source_issue(primary, strict=require_identity):
                        reject_candidate(candidate, issue, "selection")
                    continue
                try:
                    source = page(entry(candidate), candidate.domain, f"fetch:{candidate.domain}")
                    saved_sources[candidate.domain] = [source.model_dump(mode="json")]
                    if issue := primary_source_issue(source, strict=require_identity):
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
        # Policy 2 keeps going past the first six candidates when rejected pages left the batch short, and stops
        # cleanly when the run cannot afford another company rather than failing on a provider cap.
        for data in checkpoint["candidates"][:12 if discovery_policy >= 2 else 6]:
            candidate = Candidate.model_validate(data)
            if candidate.domain in researched or candidate.domain in checkpoint.get("candidate_failures", {}):
                continue
            if len(store.get_run(run_id)["records"]) >= checkpoint.get("company_limit", 3):
                break
            if issue := candidate_issue(candidate):
                reject_candidate(candidate, issue, "research")
                continue
            saved_sources = checkpoint.setdefault("sources", {})
            model_room = (room_for("model", f"model:{candidate.domain}", f"verify:{candidate.domain}")
                          if discovery_policy >= 3 else room("model", 2))
            fetch_room = (room_for("fetch", f"fetch:{candidate.domain}") if discovery_policy >= 3 else room("fetch", 1))
            if discovery_policy >= 2 and not (model_room and (candidate.domain in saved_sources or fetch_room)):
                checkpoint["research_budget_reached"] = True
                break
            billable = False
            try:
                if candidate.domain not in saved_sources:
                    source = page(entry(candidate), candidate.domain, f"fetch:{candidate.domain}")
                    saved_sources[candidate.domain] = [source.model_dump(mode="json")]
                    store.checkpoint(run_id, fence, "research", checkpoint)
                sources = tuple(Source.model_validate(s) for s in saved_sources[candidate.domain])
                if issue := primary_source_issue(sources[0], strict=require_identity):
                    reject_candidate(candidate, issue, "research")
                    continue
                # Initial-page links define the entire follow-up frontier. Never recurse.
                completed_pages = checkpoint.setdefault("completed_pages", {}).setdefault(candidate.domain, [])
                failures = checkpoint.setdefault("page_failures", {}).setdefault(candidate.domain, {})
                # Policy 3 also reads the page search found when research started from the homepage instead. The
                # partner-programme pages that made NICE, Hitachi Energy and Lumen targets (18 October) were never read.
                found = candidate.url
                if (discovery_policy >= 3 and len(sources) < 3 and found != entry(candidate) and found not in completed_pages
                        and found not in failures and room_for("fetch", f"fetch:{candidate.domain}:found")):
                    try:
                        found_page = page(found, candidate.domain, f"fetch:{candidate.domain}:found")
                        if found_page.url not in {s.url for s in sources}:
                            sources = (sources[0], found_page, *sources[1:])
                            saved_sources[candidate.domain] = [s.model_dump(mode="json") for s in sources]
                        completed_pages.append(found)
                    except FetchError as exc:
                        failures[found] = str(exc)
                    store.checkpoint(run_id, fence, "research", checkpoint)
                for index, link in enumerate(sources[0].research_links):
                    if discovery_policy >= 3 and len(sources) >= 3:
                        break
                    if link in completed_pages or link in failures or link in {s.url for s in sources}:
                        continue
                    if discovery_policy >= 2 and not (room_for("fetch", f"fetch:{candidate.domain}:page:{index + 1}")
                                                     if discovery_policy >= 3 else room("fetch", 1)):
                        break  # Research the pages already saved rather than stop the run on the fetch cap.
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
                                **prompt_inputs(), **({"company_identity_policy": 1} if require_identity else {})}
                # Quotes found on no saved page are kept for diagnosis only; they are never shown as evidence.
                rejected = []
                identity_options = {"require_identity": require_identity, "rejected": rejected} if isinstance(model, Gemma) else {}
                if previous is None:
                    try:
                        record = call("model", model.name, f"model:{candidate.domain}",
                                      lambda c=candidate, s=sources, options=identity_options: model.research(profile, c, s, **options),
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
                                      lambda c=candidate, s=sources, p=repair_input, options=identity_options: model.research(profile, c, s, repair=p, **options),
                                      {**model_inputs, "repair": repair_input},
                                      Research.model_validate)
                    except ModelOutputError as exc:
                        diagnostics[candidate.domain]["repair_failure"] = exc.diagnostic()
                        store.checkpoint(run_id, fence, "research", checkpoint)
                        raise
                if rejected:
                    checkpoint.setdefault("rejected_quotes", {})[candidate.domain] = rejected[-12:]
                billable = True
            except CompanyPageError as exc:
                reject_candidate(candidate, str(exc), "research")
                continue
            except (ProviderError, FetchError) as exc:
                if require_identity and isinstance(model, Gemma):
                    reject_candidate(candidate, "Company identity could not be established: " + str(exc), "research")
                    continue
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
                    # Policy 3 asks once more about only the assessments the verifier left out, when the run can
                    # afford it; anything still unjudged stays unverified.
                    missed = unjudged(profile, record, audit)
                    if missed and discovery_policy >= 3 and room_for("model", f"verify:{candidate.domain}:missing"):
                        pending = narrowed(record, missed)
                        try:
                            extra = call("model", model.name, f"verify:{candidate.domain}:missing",
                                         lambda r=pending: model.verify(profile, r),
                                         {"profile": profile.model_dump(mode="json"),
                                          "research": pending.model_dump(mode="json", exclude={
                                              key for key in ("company_facts", "people") if not getattr(pending, key)}),
                                          "model": settings.gemma_model, "endpoint": settings.gemma_base_url,
                                          "verification_policy": 2, **prompt_inputs()}, Verification.model_validate)
                            audit = Verification(judgments=[*audit.judgments,
                                                            *(j for j in extra.judgments if j.assessment_id in missed)])
                        except (ProviderError, BudgetExceeded):
                            pass  # The first verification stands; the skipped assessments stay unverified.
                    record = apply_verification(profile, record, audit)
                    checkpoint.setdefault("verification", {})[candidate.domain] = audit.model_dump(mode="json")
                except CompanyPageError as exc:
                    reject_candidate(candidate, str(exc), "research")
                    continue
                except (ProviderError, BudgetExceeded) as exc:
                    billable = False
                    if record.company_identity:
                        reject_candidate(candidate, "Company identity could not be verified: " + str(exc), "research")
                        continue
                    record = unavailable(profile, record, str(exc))
                    checkpoint.setdefault("verification", {})[candidate.domain] = {"error": str(exc)}
            if issue := record_issue(record, strict=True):
                reject_candidate(candidate, issue, "research")
                continue
            store.save_record(run_id, fence, record, billable=billable)
            store.event(run_id, fence, ProgressUpdate(phase="research", label="Saved research for " + candidate.domain,
                                                       state="succeeded"))
            store.checkpoint(run_id, fence, "research", checkpoint)
        records = store.get_run(run_id)["records"]
        incomplete_pages = any(checkpoint.get("page_failures", {}).values()) or bool(checkpoint.get("activity_failures"))
        incomplete_discovery = bool(checkpoint.get("discovery_failures")) or bool(checkpoint.get("use_saved_discovery"))
        short = bool(checkpoint.get("research_budget_reached")) and len(records) < checkpoint.get("company_limit", 3)
        partial = (not records or incomplete_pages or incomplete_discovery or short
                   or any(r["research"]["status"] == "partial" for r in records))
        store.event(run_id, fence, ProgressUpdate(phase="review", label=f"Saved {len(records)} companies for your review",
                                                   state="waiting"))
        store.checkpoint(run_id, fence, "review", checkpoint, "partial" if partial else "ready",
                         ("No readable company evidence could be collected" if checkpoint.get("candidate_failures")
                          else "Every company found is already in an earlier shortlist for this offer. Try another target or campaign."
                          if checkpoint.get("previously_researched") and not checkpoint.get("candidates")
                          else "No candidate companies found") if not records else
                         "Some linked company pages could not be fetched; review the saved sources." if incomplete_pages else
                         "Discovery was incomplete; these records use the candidates that were saved." if incomplete_discovery else
                         f"Research stopped at this run's provider limit with {len(records)} of {checkpoint.get('company_limit', 3)} "
                         "companies. Unused credits are returned." if short else None)
    except (ProviderError, FetchError, BudgetExceeded, Conflict) as exc:
        # Lost lease cannot write; the replacement worker owns the current state.
        try:
            store.event(run_id, fence, ProgressUpdate(phase="seller" if run["stage"] == "seller" else "research",
                                                       label=str(exc)[:400], state="failed"))
            store.checkpoint(run_id, fence, run["stage"], checkpoint, "partial", str(exc))
        except Conflict:
            pass
    return True


def execute_draft(store, settings: Settings, draft_id: str, *, model: Gemma | None = None,
                  fetch: Callable[..., Source] = fetch_page) -> bool:
    """A draft before signup: one page fetch and one model call, never a search. The page text is untrusted input;
    only a validated offer draft is saved. Failures keep the saved page so a claimed run need not fetch it again."""
    website = store.lease_anonymous_draft(draft_id)
    if website is None:
        return False
    events: list[dict] = []

    def note(label: str, state: str, *, save: bool = True):
        events.append({"label": label, "state": state, "created_at": utcnow().isoformat()})
        if save:
            store.save_anonymous_draft(draft_id, events=events)

    host = domain_of(website)
    source = None
    try:
        note("Reading " + host, "started")
        source = fetch(website)
        if source.company_domain != host:
            raise FetchError("The page moved to a different website")
        note("Saved the page from " + host, "succeeded")
        note("Drafting what you sell, who to look for and fit checks", "started")
        model = model or Gemma(settings)
        draft = model.seller(source, output_protocol=3) if isinstance(model, Gemma) else model.seller(source)
        draft = SellerDraft.model_validate(draft)
        note("Drafted your offer, target and fit checks", "succeeded", save=False)
        store.save_anonymous_draft(draft_id, events=events, status="ready", source=source.model_dump_json(),
                                   draft=draft.model_dump_json())
    except (FetchError, ProviderError, ValueError):
        # Provider and page details stay in the worker; the visitor's view gets a plain next step.
        reason = ("We couldn't read that website. Sign in to enter your offer and target yourself."
                  if source is None else "We couldn't draft from that page. Sign in to continue; your research starts again.")
        note(reason, "failed", save=False)
        store.save_anonymous_draft(draft_id, events=events, status="failed", error=reason,
                                   source=source.model_dump_json() if source is not None else None)
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
    # Drafts before signup need migration 011; an older database keeps working without them until it is migrated.
    drafts = settings.mode == "hosted" and store.anonymous_drafts_available()

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
            if drafts:
                for draft_id in store.pending_anonymous_drafts():
                    if stopped.is_set():
                        break
                    execute_draft(store, settings, draft_id)
            if once:
                return
            stopped.wait(2)
    finally:
        stopped.set()
        thread.join(timeout=5)
        store.remove_worker(worker_id)
