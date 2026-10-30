"""Stage A3-A4: competitors proven by quotes, and the automatic disqualifier rules."""
import json
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor

from shortlist.agent.answers import (
    CandidatesAnswer,
    ClassificationsAnswer,
    QuoteAnswer,
    ground_quotes,
    page_block,
)
from shortlist.agent.llm import UNTRUSTED, Calls
from shortlist.agent.models import Competitor, DisqualifierRule, DroppedClaim, SellerProfile
from shortlist.agent.pages import JOB_HOSTS, NEWS_HOSTS, REVIEW_HOSTS, Fetcher, Page
from shortlist.agent.providers import WEB_SEARCH_TOOL, search_label
from shortlist.agent.scan import rule_id
from shortlist.fetch import FetchError, canonical_url, domain_of
from shortlist.relevance import DIRECTORIES, NON_COMPANY_SITES, listed_site

MAX_COMPETITORS = 8
NOT_COMPANIES = DIRECTORIES | NON_COMPANY_SITES | REVIEW_HOSTS | NEWS_HOSTS | JOB_HOSTS

SEARCH_INSTRUCTIONS = f"""You find a B2B seller's competitors with web search. {UNTRUSTED}
Search for things like "<seller> alternatives", "<seller> vs", the product category on review sites, and read the
seller's own comparison pages if listed. At most 3 searches.
Return only JSON: {{"candidates": [{{"name": "company", "domain": "company.com", "url": "https://...",
"found_via": "the search or page where you saw it"}}]}}
List up to 8 companies that sell their own product. Never list review sites, directories, articles or people."""

CLASSIFY_INSTRUCTIONS = f"""You decide which companies compete with a seller, using only each company's own homepage text.
{UNTRUSTED}
For each company return:
- classification "direct" only when its page shows the SAME JOB (it sells the same kind of product or service) AND the
  SAME BUYER (to the same kind of companies or teams); "adjacent" when only one holds; otherwise "not_competitor".
- same_job_quote and same_buyer_quote: exact words copied from that company's page, or null.
- reason: one short sentence.
Return only JSON: {{"competitors": [{{"domain": "...", "name": "...", "classification": "...",
"same_job_quote": "...", "same_buyer_quote": "...", "reason": "..."}}]}}"""


def clean_domain(value: str) -> str | None:
    value = (value or "").strip()
    if not value:
        return None
    if "://" not in value:
        value = "https://" + value.split("/")[0]
    try:
        return domain_of(canonical_url(value))
    except FetchError:
        return None


def company_domain_issue(domain: str, seller_domain: str) -> str | None:
    if domain == seller_domain or domain.endswith("." + seller_domain):
        return "This is your own website"
    if listed_site(domain, NOT_COMPANIES):
        return "Review site, directory, job board or news site, not a company"
    return None


def find_competitors(profile: SellerProfile, seller_pages: list[str], calls: Calls, fetcher: Fetcher,
                     emit: Callable[..., None], dropped: list[DroppedClaim]) -> list[Competitor]:
    data = {"seller": profile.name or profile.domain, "website": profile.website,
            "offer": profile.offer.value if profile.offer else "", "buyer": profile.buyer.value if profile.buyer else "",
            "seller_comparison_pages": seller_pages}
    answer, turn = calls.investigator_json(
        "competitor_search", CandidatesAnswer, instructions=SEARCH_INSTRUCTIONS, tools=[WEB_SEARCH_TOOL],
        input=[{"role": "user", "content": "<data>\n" + json.dumps(data) + "\n</data>"}], max_output_tokens=2000,
        max_searches=3)
    for search in turn.searches:
        emit("competitors", f"Searched {search_label(search.query)} ({len(search.results)} results)")
    candidates: dict[str, tuple[str, str]] = {}
    for item in answer.candidates:
        domain = clean_domain(item.domain or item.url)
        if domain and not company_domain_issue(domain, profile.domain) and domain not in candidates:
            candidates[domain] = (item.name.strip()[:200] or domain, (item.found_via or "web search")[:500])
        if len(candidates) >= MAX_COMPETITORS:
            break
    if not candidates:
        emit("competitors", "No competitor candidates found", level="warn")
        return []

    unread: dict[str, str] = {}

    def read(domain: str) -> tuple[str, Page | None]:
        try:
            return domain, fetcher(f"https://{domain}/", domain)
        except FetchError as exc:
            emit("competitors", f"Could not read {domain}: {exc}", level="warn")
            unread[domain] = str(exc)[:200]
            return domain, None

    with ThreadPoolExecutor(max_workers=4) as pool:
        homepages = {domain: page for domain, page in pool.map(read, candidates) if page is not None}
    calls.meter.fetched(len(candidates))
    # A candidate whose site blocks reading cannot be proven a competitor, but dropping it hid the best-known rival in
    # a live run (drata.com, HTTP 403, for vanta.com). It stays listed as an unverified adjacent competitor: never a
    # disqualifier on its own, never a prospect, and one click makes it direct.
    unverified = [Competitor(name=candidates[domain][0], domain=domain, classification="adjacent",
                             reason=f"Not verified: its site could not be read ({error}). Mark it as a direct competitor "
                                    "if it sells the same thing to your buyers.", found_via=candidates[domain][1][:500])
                  for domain, error in unread.items()]
    if not homepages:
        return unverified
    blocks = "\n\n".join(page_block(page, 3000) for page in homepages.values())
    request = {"seller_offer": data["offer"], "seller_buyer": data["buyer"]}
    answer, _ = calls.investigator_json(
        "competitor_classify", ClassificationsAnswer, instructions=CLASSIFY_INSTRUCTIONS,
        input=[{"role": "user", "content": json.dumps(request) + "\n<data>\n" + blocks + "\n</data>"}],
        max_output_tokens=3000)
    competitors = []
    for item in answer.competitors:
        domain = clean_domain(item.domain)
        page = homepages.get(domain or "")
        if page is None:
            continue
        pages = {page.url: page}

        def quote(text, claim, page=page, domain=domain, pages=pages):
            if not text:
                return None
            found = ground_quotes([QuoteAnswer(quote=text, url=page.url)], pages, stage="competitors", dropped=dropped,
                                  claim_type=claim, source_type="competitor_site", company=domain, limit=1)
            return found[0] if found else None

        job, buyer = quote(item.same_job_quote, "same job"), quote(item.same_buyer_quote, "same buyer")
        kind = item.classification.strip().casefold().replace("-", "_").replace(" ", "_")
        kind = kind if kind in ("direct", "adjacent") else "not_competitor"
        reason = item.reason.strip()[:600]
        if kind == "direct" and not (job and buyer):
            kind = "adjacent" if (job or buyer) else "not_competitor"
            reason = "Downgraded: the page did not show both the same job and the same buyer in exact words. " + reason
        if kind == "adjacent" and not (job or buyer):
            kind, reason = "not_competitor", "No exact words on its page showed overlap. " + reason
        name, found_via = candidates[domain]
        competitors.append(Competitor(name=item.name.strip()[:200] or name, domain=domain, classification=kind,
                                      same_job=job, same_buyer=buyer, reason=reason[:600], found_via=found_via))
    competitors += unverified
    order = {"direct": 0, "adjacent": 1, "not_competitor": 2}
    competitors.sort(key=lambda c: order[c.classification])
    direct = sum(c.classification == "direct" for c in competitors)
    emit("competitors", f"Found {direct} direct competitors among {len(competitors)} candidates", level="done")
    return competitors


def disqualifier_rules(profile: SellerProfile | None, competitors: list[Competitor]) -> list[DisqualifierRule]:
    rules = [DisqualifierRule(id=rule_id(c.domain), rule="uses_direct_competitor", competitor_domain=c.domain,
                              text=f"Currently uses {c.name} ({c.domain}), a direct competitor")
             for c in competitors if c.classification == "direct"]
    rules += [DisqualifierRule(id="is_competitor", rule="is_competitor", text="Is itself a direct competitor"),
              DisqualifierRule(id="is_existing_customer", rule="is_existing_customer", text="Is already your customer")]
    if profile and profile.stated_limits:
        served = "; ".join(f"{limit.kind}: {limit.value}" for limit in profile.stated_limits)
        rules.append(DisqualifierRule(id="outside_stated_size_or_region", rule="outside_stated_size_or_region",
                                      text=f"Outside the size or region you say you serve ({served})"[:500]))
    rules.append(DisqualifierRule(id="inactive", rule="inactive",
                                  text="No longer operating: closed, acquired and shut, or the site is parked"))
    return rules
