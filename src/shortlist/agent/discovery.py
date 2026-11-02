"""Stage B: find companies that match the buyer and criteria, plus lookalikes of named customers."""
import json
import re
from collections.abc import Callable
from urllib.parse import urlsplit

from shortlist.agent.answers import CompaniesAnswer
from shortlist.agent.competitors import clean_domain, company_domain_issue
from shortlist.agent.jobboards import BOARD_PAGE, JobBoards, board_refs
from shortlist.agent.llm import UNTRUSTED, Calls
from shortlist.agent.models import MAX_COMPANIES, CandidateRef, Competitor, SellerProfile, SetAside
from shortlist.agent.providers import WEB_SEARCH_TOOL, search_label
from shortlist.agent.storage import VERDICT_LABEL
from shortlist.agent.telemetry import BudgetReached
from shortlist.domain import Candidate
from shortlist.fetch import FetchError, canonical_url
from shortlist.relevance import (
    RECRUITING_BUYER,
    candidate_issue,
    company_page_issue,
    product_target,
    staffing_firm,
)
from shortlist.selection import discussion_page

DISCOVERY_INSTRUCTIONS = f"""You find companies that could buy a seller's product now, using web search. {UNTRUSTED}
Search for the seller's need and timing signals happening now, not for a category. Spread your searches across kinds
of signal, so the companies are not all found the same way:
- hiring (at most 2 searches): a role named in the need signals on companies' own job boards: jobs.lever.co,
  boards.greenhouse.io, job-boards.greenhouse.io, jobs.ashbyhq.com or jobs.smartrecruiters.com (for example:
  site:jobs.lever.co "founding account executive"). A posting there is open now and names the company that posted
  it. A LinkedIn job result may name a company too; its role is then confirmed on the company's own board.
- news (at least 1 search): news from the last six months about an event in the timing signals, such as a funding
  round, a launch or an expansion. Name the company the news is about, never the publisher.
- social (1 search): public LinkedIn or X posts announcing such an event or a hiring push, for example
  site:linkedin.com/posts "we're hiring" "first SDR" or site:x.com "just raised" seed. A post counts only when it
  names the company that is hiring or announcing; a recruiter's post about an unnamed client names nobody.
- lookalike (only when named_customers is not empty, at most 1 search): companies similar to a named customer.
Name each company with its own website domain, never a job board's, news site's or social network's.
Aim for companies this seller can realistically win: within target_size (the size and stage the seller serves) and
like its named customers. Leave out companies clearly bigger or later-stage than target_size, and household-name
enterprises and category leaders unless the seller says it serves enterprises.
Never return list articles, directories, review sites, news sites, job boards, the seller, its competitors, its
existing customers, or people. At most 4 searches.
Return only JSON: {{"companies": [{{"name": "company", "domain": "company.com", "url": "https://company.com/",
"found_via": "the signal you saw and where, for example 'job post: SDR (Greenhouse, 12 Oct 2026)' or 'similar to <customer>'",
"posting_url": "the job posting's own url when found_via is a job post, else empty",
"source_url": "the news article or post where you saw the signal, else empty",
"signal": "hiring|news|social|lookalike"}}]}}"""


def excluded_domains(profile: SellerProfile, competitors: list[Competitor]) -> dict[str, str]:
    excluded = {profile.domain: "This is your own website"}
    for competitor in competitors:
        if competitor.classification != "not_competitor":
            excluded[competitor.domain] = f"Known {competitor.classification} competitor"
    for customer in profile.existing_customers:
        if customer.domain:
            excluded[customer.domain] = "Already your customer (named on your site)"
    return excluded


STAFFING_ASIDE = "Recruiting or staffing firm: its job posts are for its clients"
SEARCH_RESULT_PAGE = ("A search result about the company, not its own homepage or product page (for example a news "
                      "article); the publisher is not a candidate")


def already_researched(entry: dict) -> str:
    return f"Already researched for you on {entry['date']}: {VERDICT_LABEL[entry['verdict']]}"


def admit(url: str, name: str, found_via: str, excluded: dict[str, str], seller_domain: str, *,
          own_page: bool = False, prior: dict[str, dict] | None = None) -> tuple[CandidateRef | None, SetAside | None]:
    """own_page: a raw search result is admitted only when it is the company's own entry page. In the first live run,
    news articles that mentioned companies made their publishers candidates. prior: companies researched for this
    seller in an earlier run, set aside with a link to that run instead of being paid for again."""
    domain = clean_domain(url)
    if domain is None:
        return None, None
    try:
        url = canonical_url(url if "://" in url else f"https://{domain}/")
    except FetchError:
        url = f"https://{domain}/"
    if prior and domain in prior:
        return None, SetAside(domain=domain, url=f"https://{domain}/", reason=already_researched(prior[domain]),
                              previous_run=prior[domain]["run_id"])
    owner = next((reason for known, reason in excluded.items() if domain == known or domain.endswith("." + known)), None)
    for reason in (owner, company_domain_issue(domain, seller_domain),
                   "Discussion thread" if discussion_page(url) else None, company_page_issue(url, name),
                   candidate_issue(Candidate(domain=domain, name=name or domain, url=url, query=found_via or "agent",
                                             provider="agent"), policy=3),
                   SEARCH_RESULT_PAGE if own_page and company_page_issue(url, name, strict=True) else None):
        if reason:
            return None, SetAside(domain=domain, url=url, reason=reason)
    # Research starts from the company's homepage; the found page was only where search saw it.
    return CandidateRef(domain=domain, name=name[:200], url=f"https://{domain}/", found_via=found_via[:500]), None


def compact(text: str) -> str:
    return re.sub(r"[^a-z0-9]", "", text.casefold())


def with_posting(item, postings: list[str]):
    """The model often names the board ("on jobs.lever.co") but not the posting; the search results hold it. A
    posting is matched only when its board's name is the company's name or domain stem. When the results hold several
    postings from that board, the board itself is kept so the open role is chosen by title: taking the first one gave
    Middesk "Lead Data Scientist" for an SDR lead."""
    if (item.posting_url and len([p for p in urlsplit(item.posting_url).path.split("/") if p]) >= 2) \
            or not postings:
        return item
    keys = {compact(item.name), compact((clean_domain(item.url or item.domain) or "").split(".")[0])} - {""}
    matches = [url for url in postings if any(compact(slug) in keys for _, slug in board_refs(url)[:1])]
    if not matches:
        return item
    if len(matches) > 1:
        platform, slug = board_refs(matches[0])[0]
        return item.model_copy(update={"posting_url": BOARD_PAGE[platform].format(slug)})
    return item.model_copy(update={"posting_url": matches[0]})


def lead(item, boards: JobBoards | None, emit: Callable[..., None]) -> str:
    """found_via for a named company. A job posting still listed on the company's own board becomes an open job post
    lead with its url, which the investigation fetches and quotes first."""
    found_via = item.found_via or "web search"
    if boards is None or not item.posting_url:
        return found_via
    names = [n for n in (item.name, (clean_domain(item.url or item.domain) or "").split(".")[0]) if n]
    match = boards.posting(item.posting_url, names, role=found_via)
    if match is None:
        return f"{found_via} (posting {item.posting_url[:200]} not confirmed open on the company's board)"
    board, opening = match
    emit("discovery", f"Confirmed open on {board.label}: {opening.title} ({item.name or item.domain})")
    when = f", posted {opening.posted.isoformat()}" if opening.posted else ""
    return f"open job post on its {board.label} board: {opening.title}{when} ({opening.url})"


def discover(profile: SellerProfile, competitors: list[Competitor], count: int, calls: Calls,
             emit: Callable[..., None], known: list[CandidateRef] | None = None, prior: dict[str, dict] | None = None,
             boards: JobBoards | None = None) -> tuple[list[CandidateRef], list[SetAside]]:
    excluded = excluded_domains(profile, competitors)
    prior = prior or {}
    pool: dict[str, CandidateRef] = {c.domain: c for c in known or []}
    set_aside: dict[str, SetAside] = {}
    wanted = min(MAX_COMPANIES, max(count, 1))
    buyer = profile.buyer.value if profile.buyer else ""
    others = product_target(buyer) and not RECRUITING_BUYER.search(buyer)  # as competitors.disqualifier_rules
    for attempt in range(2):
        if len(pool) >= wanted:
            break
        data = {"offer": profile.offer.value if profile.offer else "", "buyer": profile.buyer.value if profile.buyer else "",
                "fit_checks": [c.text for c in profile.fit_criteria if c.enabled],
                # Search by what a buying company does now; category searches returned lists of the largest brands.
                "target_size": profile.target_size.value if profile.target_size else "small and mid-sized companies",
                "need_signals": [s.text for s in profile.need_signals],
                "timing_signals": [s.text for s in profile.timing_signals],
                "served": [f"{limit.kind}: {limit.value}" for limit in profile.stated_limits],
                "named_customers": [c.domain or c.name for c in profile.existing_customers][:10],
                # Companies researched for this seller before come last, so the newest exclusions are never cut off.
                "do_not_return": (sorted(set(excluded) | set(pool)) + list(prior))[:80], "how_many": wanted * 2}
        try:
            answer, turn = calls.investigator_json(
                "discovery", CompaniesAnswer, instructions=DISCOVERY_INSTRUCTIONS, tools=[WEB_SEARCH_TOOL],
                input=[{"role": "user", "content": "<data>\n" + json.dumps(data) + "\n</data>"}], max_output_tokens=3000,
                max_searches=4)
        except BudgetReached:
            if not pool:
                raise
            # Keep what the first search found: those companies are shown as stopped by the budget, not lost.
            emit("discovery", "Run budget reached; keeping the companies already found", level="warn")
            break
        # Companies the model named come first; raw search results only when they are a company's own page.
        postings = [result.url for search in turn.searches for result in search.results if board_refs(result.url)]
        seen = {result.url for search in turn.searches for result in search.results}
        found = [(item.url or item.domain, item.name, lead(with_posting(item, postings), boards, emit), False,
                  signal_of(item.signal, item.found_via), source_link(item.source_url, seen))
                 for item in answer.companies]
        for search in turn.searches:
            emit("discovery", f"Searched {search_label(search.query)} ({len(search.results)} results)")
            found += [(result.url, result.title, f'search "{search.query}"', True, signal_of("", search.query), "")
                      for result in search.results]
        for url, name, via, own_page, signal, source in found:
            ref, aside = admit(url, name or "", via, excluded, profile.domain, own_page=own_page, prior=prior)
            if ref and others and staffing_firm(name or ""):
                ref, aside = None, SetAside(domain=ref.domain, url=ref.url, reason=STAFFING_ASIDE)
            if ref and ref.domain not in pool and len(pool) < MAX_COMPANIES:
                pool[ref.domain] = ref.model_copy(update={"signal": signal, "source_url": source})
            elif aside and aside.domain not in pool:
                set_aside.setdefault(aside.domain, aside)
        if not answer.companies and not turn.searches:
            break
    set_aside = {domain: aside for domain, aside in set_aside.items() if domain not in pool}
    seen = sum(1 for aside in set_aside.values() if aside.previous_run)
    emit("discovery", f"Found {len(pool)} candidate companies; set aside {len(set_aside)} pages "
                      "(lists, directories, competitors, customers"
                      + (f", {seen} already researched for you" if seen else "") + ")", level="done")
    return interleaved(list(pool.values())), list(set_aside.values())


SIGNALS = ("hiring", "news", "social", "lookalike")


def source_link(url: str, seen: set[str]) -> str:
    """Where discovery saw a company's signal, kept only when that page was one of its search results: a model-written
    link can be invented (greenlight.com's job link answered 404)."""
    url = (url or "").strip()
    return url[:2048] if url.startswith("https://") and url in seen else ""


def signal_of(declared: str, via: str) -> str:
    """The kind of signal a company was found by: the model's own label, else read from how it was found."""
    if (declared := (declared or "").strip().casefold()) in SIGNALS:
        return declared
    via = (via or "").casefold()
    if not via:
        return ""
    if "job post" in via or re.search(r"lever\.co|greenhouse\.io|ashbyhq\.com|smartrecruiters\.com|linkedin\.com/jobs", via):
        return "hiring"
    if "similar to" in via:
        return "lookalike"
    if re.search(r"linkedin\.com|\bx\.com|twitter\.com", via):
        return "social"
    return "news"


def interleaved(refs: list[CandidateRef]) -> list[CandidateRef]:
    """One company of each signal in turn, so the first researched are not all found the same way: live runs
    researched only job-post leads and missed every company with a funding round or a launch."""
    groups: dict[str, list[CandidateRef]] = {}
    for ref in refs:
        groups.setdefault(ref.signal, []).append(ref)
    ordered = []
    while any(groups.values()):
        for group in groups.values():
            if group:
                ordered.append(group.pop(0))
    return ordered
