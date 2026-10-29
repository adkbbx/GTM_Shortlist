"""Stage B: find companies that match the buyer and criteria, plus lookalikes of named customers."""
import json
from collections.abc import Callable

from shortlist.agent.answers import CompaniesAnswer
from shortlist.agent.competitors import clean_domain, company_domain_issue
from shortlist.agent.llm import UNTRUSTED, Calls
from shortlist.agent.models import MAX_COMPANIES, CandidateRef, Competitor, SellerProfile, SetAside
from shortlist.agent.providers import WEB_SEARCH_TOOL
from shortlist.domain import Candidate
from shortlist.fetch import FetchError, canonical_url
from shortlist.relevance import candidate_issue, company_page_issue
from shortlist.selection import discussion_page

DISCOVERY_INSTRUCTIONS = f"""You find companies that could buy a seller's product, using web search. {UNTRUSTED}
Search for companies that match the buyer and fit checks, and companies similar to the seller's named customers.
Prefer each company's own website. Never return list articles, directories, review sites, news stories, the seller,
its competitors, its existing customers, or people. At most 4 searches.
Return only JSON: {{"companies": [{{"name": "company", "domain": "company.com", "url": "https://company.com/",
"found_via": "the search, or 'similar to <customer>'"}}]}}"""


def excluded_domains(profile: SellerProfile, competitors: list[Competitor]) -> dict[str, str]:
    excluded = {profile.domain: "This is your own website"}
    for competitor in competitors:
        if competitor.classification != "not_competitor":
            excluded[competitor.domain] = f"Known {competitor.classification} competitor"
    for customer in profile.existing_customers:
        if customer.domain:
            excluded[customer.domain] = "Already your customer (named on your site)"
    return excluded


def admit(url: str, name: str, found_via: str, excluded: dict[str, str], seller_domain: str
          ) -> tuple[CandidateRef | None, SetAside | None]:
    domain = clean_domain(url)
    if domain is None:
        return None, None
    try:
        url = canonical_url(url if "://" in url else f"https://{domain}/")
    except FetchError:
        url = f"https://{domain}/"
    owner = next((reason for known, reason in excluded.items() if domain == known or domain.endswith("." + known)), None)
    for reason in (owner, company_domain_issue(domain, seller_domain),
                   "Discussion thread" if discussion_page(url) else None, company_page_issue(url, name),
                   candidate_issue(Candidate(domain=domain, name=name or domain, url=url, query=found_via or "agent",
                                             provider="agent"), policy=3)):
        if reason:
            return None, SetAside(domain=domain, url=url, reason=reason)
    # Research starts from the company's homepage; the found page was only where search saw it.
    return CandidateRef(domain=domain, name=name[:200], url=f"https://{domain}/", found_via=found_via[:500]), None


def discover(profile: SellerProfile, competitors: list[Competitor], count: int, calls: Calls,
             emit: Callable[..., None], known: list[CandidateRef] | None = None
             ) -> tuple[list[CandidateRef], list[SetAside]]:
    excluded = excluded_domains(profile, competitors)
    pool: dict[str, CandidateRef] = {c.domain: c for c in known or []}
    set_aside: dict[str, SetAside] = {}
    wanted = min(MAX_COMPANIES, max(count, 1))
    for attempt in range(2):
        if len(pool) >= wanted:
            break
        data = {"offer": profile.offer.value if profile.offer else "", "buyer": profile.buyer.value if profile.buyer else "",
                "fit_checks": [c.text for c in profile.fit_criteria if c.enabled],
                "served": [f"{limit.kind}: {limit.value}" for limit in profile.stated_limits],
                "named_customers": [c.domain or c.name for c in profile.existing_customers][:10],
                "do_not_return": sorted(set(excluded) | set(pool))[:60], "how_many": wanted * 2}
        answer, turn = calls.investigator_json(
            "discovery", CompaniesAnswer, instructions=DISCOVERY_INSTRUCTIONS, tools=[WEB_SEARCH_TOOL],
            input=[{"role": "user", "content": "<data>\n" + json.dumps(data) + "\n</data>"}], max_output_tokens=3000)
        found = [(item.url or item.domain, item.name, item.found_via or "web search") for item in answer.companies]
        for search in turn.searches:
            emit("discovery", f'Searched "{search.query}" ({len(search.results)} results)')
            found += [(result.url, result.title, f'search "{search.query}"') for result in search.results]
        for url, name, via in found:
            ref, aside = admit(url, name or "", via, excluded, profile.domain)
            if ref and ref.domain not in pool and len(pool) < MAX_COMPANIES:
                pool[ref.domain] = ref
            elif aside and aside.domain not in pool:
                set_aside.setdefault(aside.domain, aside)
        if not answer.companies and not turn.searches:
            break
    set_aside = {domain: aside for domain, aside in set_aside.items() if domain not in pool}
    emit("discovery", f"Found {len(pool)} candidate companies; set aside {len(set_aside)} pages "
                      "(lists, directories, competitors, customers)", level="done")
    return list(pool.values()), list(set_aside.values())
