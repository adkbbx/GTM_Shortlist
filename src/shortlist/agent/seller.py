"""Stage A: understand the seller from its own website, with no typing required."""
import json
import re
from collections.abc import Callable

from shortlist.agent.answers import SellerAnswer, ground_quotes, page_block
from shortlist.agent.llm import UNTRUSTED, Calls
from shortlist.agent.models import (
    DroppedClaim,
    ExistingCustomer,
    FitCriterion,
    Interpretation,
    PageRef,
    SellerProfile,
    Signal,
    StatedLimit,
    Statement,
)
from shortlist.agent.pages import Fetcher, Page, comparison_links, seller_links
from shortlist.fetch import FetchError, canonical_url, domain_of

SELLER_INSTRUCTIONS = f"""You read a B2B seller's own website and describe, for a prospecting tool, what it sells and
which companies would buy it. {UNTRUSTED}

Return only one JSON object with this shape:
{{"name": "seller name",
 "offer": {{"value": "what they sell, one sentence", "quotes": [{{"quote": "exact words", "url": "page url"}}]}},
 "buyer": {{"value": "which companies buy it, one sentence", "quotes": [...]}},
 "existing_customers": [{{"name": "customer company", "domain": "customer.com or null", "quotes": [...]}}],
 "fit_criteria": [{{"id": "fit-1", "text": "an observable check on a company's own pages", "required": true, "quotes": [...]}}],
 "need_signals": [{{"id": "need-1", "text": "something a company does that shows it needs this", "quotes": [...]}}],
 "timing_signals": [{{"id": "timing-1", "text": "an event that makes now a good time", "quotes": [...]}}],
 "stated_limits": [{{"kind": "size or region", "value": "...", "quotes": [...]}}],
 "interpretations": [{{"offer": "...", "buyer": "...", "quotes": [...]}}]}}

Rules:
- Every quote is copied exactly, word for word, from one page's text, with that page's url. No paraphrase.
- fit_criteria: 2 to 5 checks that can be observed on a target company's website (what it sells, how it sells,
  what it runs). Mark each required or not.
- need_signals: 2 to 4, such as hiring a role the product replaces or using an older tool the product replaces.
- timing_signals: up to 3, such as a launch, expansion or new funding.
- existing_customers: only companies the site names as customers (logos, case studies, testimonials).
- stated_limits: only a company size or region the site explicitly says it serves. Otherwise an empty list.
- Describe companies only. Never name, describe or judge individual people.
- If the site is too vague to tell the offer or the buyer, leave that field null and give up to 3 different
  interpretations, each with a quote it rests on."""


def choose_pages(home: Page, extra: int = 5) -> list[str]:
    """Up to five same-domain pages: pricing, product, customers, about, integrations, keeping one slot for the
    seller's own comparison page when it has one."""
    compare = comparison_links(home)[:1]
    links = [link for link in seller_links(home, extra - len(compare)) if link not in compare]
    return (links + compare)[:extra]


def read_seller_pages(website: str, fetcher: Fetcher, emit: Callable[..., None]) -> dict[str, Page]:
    home = fetcher(website, None)
    pages = {home.url: home}
    emit("seller", f"Read your homepage ({home.url})")
    for link in choose_pages(home):
        try:
            page = fetcher(link, home.domain)
        except FetchError as exc:
            emit("seller", f"Could not read {link}: {exc}", level="warn")
            continue
        pages[page.url] = page
        emit("seller", f"Read {page.url}")
    return pages


def _criterion_id(prefix: str, raw: str, index: int, used: set[str]) -> str:
    value = re.sub(r"[^a-z0-9-]+", "-", (raw or "").casefold()).strip("-")[:40]
    value = value if value and value not in used else f"{prefix}-{index + 1}"
    while value in used:
        value += "-x"
    used.add(value)
    return value


def build_profile(website: str, answer: SellerAnswer, pages: dict[str, Page], dropped: list[DroppedClaim]) -> SellerProfile:
    home = next(iter(pages.values()))

    def quotes(items, claim_type, limit=3):
        return ground_quotes(items, pages, stage="seller", dropped=dropped, claim_type=claim_type,
                             source_type="own_site", limit=limit)

    def statement(item, claim_type):
        if item is None or not item.value.strip():
            return None
        found = quotes(item.quotes, claim_type)
        return Statement(value=item.value.strip()[:1000], quotes=found) if found else None

    used: set[str] = set()
    criteria = []
    for index, item in enumerate(answer.fit_criteria[:8]):
        found = quotes(item.quotes, "fit criterion")
        if len(item.text.strip()) >= 3 and found:
            criteria.append(FitCriterion(id=_criterion_id("fit", item.id, index, used), text=item.text.strip()[:500],
                                         required=item.required, quotes=found))
    signals = {}
    for kind, items, cap in (("need", answer.need_signals, 4), ("timing", answer.timing_signals, 3)):
        kept = []
        for index, item in enumerate(items[:6]):
            found = quotes(item.quotes, f"{kind} signal")
            if len(item.text.strip()) >= 3 and found:
                kept.append(Signal(id=_criterion_id(kind, item.id, index, used), kind=kind,
                                   text=item.text.strip()[:500], quotes=found))
        signals[kind] = kept[:cap]
    customers = []
    for item in answer.existing_customers[:30]:
        found = quotes(item.quotes, "existing customer", limit=2)
        if not item.name.strip() or not found:
            continue
        domain = None
        if item.domain:
            try:
                domain = domain_of(canonical_url("https://" + item.domain.strip().removeprefix("https://")
                                                 .removeprefix("http://").split("/")[0]))
            except FetchError:
                domain = None
        customers.append(ExistingCustomer(name=item.name.strip()[:200], domain=domain, quotes=found))
    limits = []
    for item in answer.stated_limits[:4]:
        kind = item.kind.strip().casefold()
        if kind not in ("size", "region"):
            continue
        found = quotes(item.quotes, "stated limit", limit=2)
        if len(item.value.strip()) >= 2 and found:
            limits.append(StatedLimit(kind=kind, value=item.value.strip()[:300], quotes=found))
    readings = []
    for item in answer.interpretations[:3]:
        found = quotes(item.quotes, "interpretation", limit=2)
        if len(item.offer.strip()) >= 3 and len(item.buyer.strip()) >= 3 and found:
            readings.append(Interpretation(id=f"reading-{len(readings) + 1}", offer=item.offer.strip()[:600],
                                           buyer=item.buyer.strip()[:600], quotes=found))
    return SellerProfile(
        website=website, domain=home.domain, name=answer.name.strip()[:200], offer=statement(answer.offer, "offer"),
        buyer=statement(answer.buyer, "buyer"), existing_customers=customers, fit_criteria=criteria[:5],
        need_signals=signals["need"], timing_signals=signals["timing"], stated_limits=limits,
        interpretations=readings,
        pages=[PageRef(url=page.url, title=page.source.title[:300], fetched_at=page.fetched_at) for page in pages.values()])


def understand_seller(website: str, calls: Calls, fetcher: Fetcher, emit: Callable[..., None],
                      dropped: list[DroppedClaim], hint: tuple[str, str] | None = None) -> SellerProfile:
    pages = read_seller_pages(website, fetcher, emit)
    blocks = "\n\n".join(page_block(page, 8000 if index == 0 else 5000) for index, page in enumerate(pages.values()))
    request = "Describe this seller from its own pages.\n"
    if hint:
        request += ("The seller chose this reading of its site; use it and propose criteria and signals for it: "
                    + json.dumps({"offer": hint[0], "buyer": hint[1]}) + "\n")
    answer, _ = calls.investigator_json("seller_profile", SellerAnswer, instructions=SELLER_INSTRUCTIONS,
                                        input=[{"role": "user", "content": request + "<data>\n" + blocks + "\n</data>"}],
                                        max_output_tokens=4000)
    profile = build_profile(website, answer, pages, dropped)
    emit("seller", f"Understood the offer with {len(profile.fit_criteria)} fit checks, "
                   f"{len(profile.need_signals)} need signals and {len(profile.existing_customers)} named customers",
         level="done")
    return profile
