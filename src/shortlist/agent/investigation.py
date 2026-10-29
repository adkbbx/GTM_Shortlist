"""Stage C: one company, one bounded agent loop. The investigator may search the web and call fetch_page; the
code fetches through the safe fetcher, scans page code for competitors and keeps only quotes found verbatim."""
import json
import re
import time
from collections import Counter
from collections.abc import Callable
from dataclasses import dataclass, field
from urllib.parse import urlsplit

from shortlist.agent.answers import InvestigationAnswer, page_for
from shortlist.agent.llm import UNTRUSTED, AgentOutputError, Calls
from shortlist.agent.models import (
    CandidateRef,
    CompanyResult,
    Competitor,
    DisqualifierRule,
    DroppedClaim,
    EvidenceItem,
    Quote,
    SellerProfile,
)
from shortlist.agent.pages import (
    Fetcher,
    Page,
    excerpt,
    ground,
    open_posting,
    parse_date,
    place_name,
    signature,
    source_type,
    verified_date,
)
from shortlist.agent.providers import FETCH_TOOL, WEB_SEARCH_TOOL, AgentProviderError, FunctionCall
from shortlist.agent.scan import brand_names, scan
from shortlist.agent.telemetry import BudgetReached
from shortlist.fetch import FetchError, canonical_url, domain_of

MAX_SEARCHES = 4
MAX_FETCHES = 6
MAX_TURNS = 8

INSTRUCTIONS = f"""You investigate ONE company for a B2B seller and collect quoted evidence. {UNTRUSTED}

Work in this order:
1. Fit: check each fit check against the company's own pages. The homepage text is supplied; call fetch_page for
   other pages on its site (product, pricing, about, careers).
2. Need and timing (spend most of your searches here): the company's own marketing cannot show need, so look
   beyond it. Search for its job posts (its careers page, or job boards such as Greenhouse, Lever, Workable or
   LinkedIn) for roles named in the need signals, and for news or press releases from the last six months for the
   timing signals. If found_via names a job post or news item, find and fetch that page first. Fetch the job post or
   article itself and quote it. Note a page's publication date only when the page states it.
3. Competitor use: ONE search that names all listed competitors together, for example
   "<company> <competitor 1> <competitor 2>"; the company's own page code is already scanned for them. Fetch a
   competitor's customer or case-study page only if a result names the company. Evidence must show CURRENT use, not
   an integration, a comparison article or past use.
Limits: at most {MAX_SEARCHES} web searches and {MAX_FETCHES} fetch_page calls in total.

Evidence rules:
- Cite only pages you fetched with fetch_page, or the supplied homepage. Search snippets are not evidence.
- Every quote is copied exactly, word for word, from that page's text, with that page's url.
- criterion_id must be one of the ids in the data.
- Describe the company only. Never name, describe or judge individual people. A job post is about a role.
- Do not invent facts, dates, quotes or buying intent. Leave out anything you could not find.

When you are done, reply with only JSON:
{{"company_name": "...", "evidence": [{{"claim_type": "fit|need|timing|disqualifier", "criterion_id": "...",
"claim": "one short sentence", "quote": "exact words", "url": "page url",
"source_type": "own_site|job_post|news|review|competitor_site|other", "published_date": "YYYY-MM-DD or null"}}]}}"""

FINAL = "Your search and fetch limits are used up. Reply now with only the final JSON evidence object."


@dataclass
class Context:
    calls: Calls
    fetcher: Fetcher
    profile: SellerProfile
    competitors: list[Competitor]
    rules: list[DisqualifierRule]
    emit: Callable[..., None]
    dropped: list[DroppedClaim] = field(default_factory=list)

    @property
    def direct(self) -> list[Competitor]:
        enabled = {rule.competitor_domain for rule in self.rules if rule.enabled and rule.competitor_domain}
        return [c for c in self.competitors if c.classification == "direct" and c.domain in enabled]


def company_names(domain: str, home: Page | None) -> list[str]:
    stem = domain.split(".")[0]
    names = {stem, stem.replace("-", " "), stem.replace("-", "")}
    if home is not None and home.source.title:
        head = re.split(r"\s[|\-–—:·]\s", home.source.title)[0].strip()
        if 4 <= len(head) <= 60:
            names.add(head)
    return [name for name in names if len(name.replace(" ", "")) >= 4]


def mentions(text: str, names: list[str], domain: str) -> str | None:
    """The first line of a page that names the company, for a competitor's customer page."""
    for line in text.splitlines():
        lowered = line.casefold()
        if domain in lowered or any(re.search(r"(?<![\w-])" + re.escape(n.casefold()) + r"(?![\w-])", lowered)
                                    for n in names):
            return line.strip()[:600]
    return None


def summarize_places(places: list[str]) -> list[str]:
    counts = Counter(places)
    summary = []
    for place, count in counts.items():
        if count == 1 or place.startswith("search "):
            summary.append(place)
        else:
            summary.append(f"{count} {place}s" if not place.endswith("s") else f"{count} {place}")
    return summary


class Investigation:
    def __init__(self, company: CandidateRef, ctx: Context):
        self.company = company
        self.ctx = ctx
        self.result = CompanyResult(domain=company.domain, name=company.name, url=company.url,
                                    found_via=company.found_via, status="investigating")
        self.pages: dict[str, Page] = {}
        self.places: list[str] = []
        self.queries: list[str] = []
        self.home: Page | None = None
        self.names: list[str] = []

    # Pages -----------------------------------------------------------------------------------------------------
    def fetch(self, url: str) -> Page:
        if self.result.fetches >= MAX_FETCHES:
            raise FetchError("Fetch limit for this company reached")
        self.result.fetches += 1
        self.ctx.calls.meter.fetched()
        expected = self.company.domain if domain_of(url) == self.company.domain else None
        page = self.ctx.fetcher(url, expected)
        self.pages[page.url] = page
        try:
            self.pages.setdefault(canonical_url(url), page)
        except FetchError:
            pass
        self.observe(page)
        return page

    def observe(self, page: Page):
        competitor_domains = {c.domain: c for c in self.ctx.competitors}
        if page.domain == self.company.domain or page.domain.endswith("." + self.company.domain):
            homepage = self.home is None or page is self.home
            sig = signature(page, homepage=homepage)
            self.result.signatures.append(sig)
            self.result.evidence += scan(sig, self.ctx.direct, self.company.name or self.company.domain)
            self.places.append("homepage code" if homepage else place_name(page.url))
            return
        owner = next((c for d, c in competitor_domains.items() if page.domain == d or page.domain.endswith("." + d)), None)
        if owner is not None:
            kind = "customer page" if re.search(r"customer|case|stor|client", urlsplit(page.url).path, re.IGNORECASE) else "page"
            self.places.append(f"{owner.name} {kind}")
            line = mentions(page.source.text, self.names, self.company.domain)
            if line and owner in self.ctx.direct:
                located = ground(line, page)
                if located:
                    self.result.evidence.append(EvidenceItem(
                        claim_type="disqualifier", criterion_id=f"uses_direct_competitor:{owner.domain}", found_by="scan",
                        claim=f"{owner.name}'s own site names {self.company.name or self.company.domain}",
                        quote=Quote(text=located[0], url=page.url, source_type="competitor_site",
                                    published_date=verified_date(None, page), fetched_at=page.fetched_at,
                                    location=located[1])))
            return
        self.places.append(f"{source_type(page.url, self.company.domain)} page on {page.domain}".replace("_", " "))

    def tool(self, call: FunctionCall) -> str:
        if call.name != "fetch_page":
            return "Unknown tool. Only fetch_page is available."
        try:
            url = json.loads(call.arguments or "{}").get("url", "")
        except (ValueError, AttributeError):
            return "Invalid arguments: give {\"url\": \"https://...\"}."
        if not isinstance(url, str) or not url:
            return "Invalid arguments: give {\"url\": \"https://...\"}."
        try:
            page = self.fetch(url)
        except FetchError as exc:
            if "limit" not in str(exc):
                self.result.blocked.append(f"{url[:300]}: {exc}")
            return f"Could not fetch this page: {exc}"
        dates = ", ".join(d.isoformat() for d in page.dates[:3])
        note = f"\nThe page declares publication date(s): {dates}" if dates else ""
        return f'<page url="{page.url}">\n{excerpt(page, 6000)}\n</page>{note}'

    # Loop ------------------------------------------------------------------------------------------------------
    def brief(self) -> str:
        profile = self.ctx.profile
        data = {
            "company": self.company.domain, "homepage": self.home.url if self.home else self.company.url,
            "seller_offer": profile.offer.value if profile.offer else "",
            "seller_buyer": profile.buyer.value if profile.buyer else "",
            "fit_checks": [{"id": c.id, "text": c.text, "required": c.required} for c in profile.fit_criteria if c.enabled],
            "need_signals": [{"id": s.id, "text": s.text} for s in profile.need_signals],
            "timing_signals": [{"id": s.id, "text": s.text} for s in profile.timing_signals],
            "disqualifier_checks": [{"id": r.id, "text": r.text} for r in self.ctx.rules
                                    if r.enabled and r.rule not in ("is_competitor", "is_existing_customer")],
            "competitors": [{"name": c.name, "domain": c.domain} for c in self.ctx.direct],
            # Discovery's lead (a job post or news item it saw); a lead to check, never evidence by itself.
            "found_via": self.company.found_via or "",
        }
        home = f'\n<page url="{self.home.url}">\n{excerpt(self.home, 6000)}\n</page>' if self.home else ""
        return "Investigate this company.\n<data>\n" + json.dumps(data) + home + "\n</data>"

    def loop(self) -> InvestigationAnswer:
        calls = self.ctx.calls
        history: list[dict] = [{"role": "user", "content": self.brief()}]
        pending = list(history)
        previous = None
        stateful = calls.investigator.continuation == "previous"
        final = None
        for index in range(MAX_TURNS):
            last = index == MAX_TURNS - 1
            tools = [] if last else ([WEB_SEARCH_TOOL] if self.result.searches < MAX_SEARCHES else []) + \
                ([FETCH_TOOL] if self.result.fetches < MAX_FETCHES else [])
            if not tools:
                note = {"role": "user", "content": FINAL}
                history.append(note)
                pending.append(note)
            turn = calls.respond("investigate", instructions=INSTRUCTIONS, input=pending if stateful and previous else history,
                                 tools=tools, company=self.company.domain, previous_response_id=previous if stateful else None,
                                 max_searches=MAX_SEARCHES - self.result.searches)
            self.result.turns += 1
            self.result.searches += turn.search_count
            for search in turn.searches:
                if search.query:
                    self.queries.append(search.query)
                    self.places.append(f'search "{search.query[:120]}"')
            if turn.function_calls and tools:
                outputs = [{"type": "function_call_output", "call_id": call.call_id, "output": self.tool(call)}
                           for call in turn.function_calls]
                history += turn.output_items + outputs
                pending = outputs
                previous = turn.response_id
                continue
            final = turn
            break
        if final is None:
            raise AgentOutputError("The investigator did not finish within its turn limit")
        return calls.repair_investigator("investigate", InvestigationAnswer, final, instructions=INSTRUCTIONS,
                                         company=self.company.domain)

    # Grounding -------------------------------------------------------------------------------------------------
    def valid_ids(self) -> dict[str, set[str]]:
        profile = self.ctx.profile
        return {"fit": {c.id for c in profile.fit_criteria if c.enabled},
                "need": {s.id for s in profile.need_signals}, "timing": {s.id for s in profile.timing_signals},
                "disqualifier": {r.id for r in self.ctx.rules if r.enabled}}

    def keep(self, answer: InvestigationAnswer):
        ids = self.valid_ids()
        competitor_domains = [c.domain for c in self.ctx.competitors]
        drop = self.ctx.dropped
        for item in answer.evidence[:40]:
            criterion = item.criterion_id.strip()
            item.claim_type = item.claim_type.strip().casefold()
            if item.claim_type not in ids:
                drop.append(DroppedClaim(stage="investigation", company=self.company.domain, claim_type=item.claim_type[:40],
                                         quote=item.quote[:1500], url=item.url[:2048], reason="Unknown claim type"))
                continue
            if criterion not in ids[item.claim_type] and item.claim_type == "disqualifier":
                named = next((c for c in self.ctx.direct if c.domain in item.claim.casefold() + criterion.casefold()
                              or any(n.casefold() in item.claim.casefold() for n in brand_names(c))), None)
                criterion = f"uses_direct_competitor:{named.domain}" if named else criterion
            if criterion not in ids[item.claim_type]:
                drop.append(DroppedClaim(stage="investigation", company=self.company.domain, claim_type=item.claim_type,
                                         quote=item.quote[:1500], url=item.url[:2048],
                                         reason=f"Unknown check id {criterion[:80]!r}"))
                continue
            named = page_for(item.url, self.pages) if item.url else None
            if named is None and item.url and self.result.fetches < MAX_FETCHES:
                try:
                    named = self.fetch(item.url)
                except FetchError as exc:
                    self.result.blocked.append(f"{item.url[:300]}: {exc}")
            located = None
            fetched = list({id(p): p for p in self.pages.values()}.values())
            for page in ([named] if named else []) + [p for p in fetched if p is not named]:
                if (found := ground(item.quote, page)) is not None:
                    located = (page, *found)
                    break
            if located is None:
                drop.append(DroppedClaim(stage="investigation", company=self.company.domain, claim_type=item.claim_type,
                                         quote=item.quote[:1500], url=item.url[:2048],
                                         reason="Quote not found in any page fetched for this company"))
                continue
            page, text, location = located
            claimed = parse_date(item.published_date)
            published = verified_date(claimed, page)
            if claimed and published != claimed:
                drop.append(DroppedClaim(stage="investigation", company=self.company.domain, claim_type="date",
                                         quote=str(item.published_date)[:40], url=page.url,
                                         reason="Date not stated on the page; the date was removed"))
            kind = source_type(page.url, self.company.domain, competitor_domains, item.source_type)
            evidence = EvidenceItem(
                claim_type=item.claim_type, criterion_id=criterion, claim=(item.claim.strip() or text)[:600],
                quote=Quote(text=text, url=page.url, published_date=published, fetched_at=page.fetched_at,
                            source_type=kind, location=location,
                            open_posting=kind == "job_post" and open_posting(page)))
            if all((e.criterion_id, e.quote.text) != (evidence.criterion_id, text) for e in self.result.evidence):
                self.result.evidence.append(evidence)

    def checked(self):
        self.result.checked_places = summarize_places(self.places)
        direct = self.ctx.direct
        searched = any(any(n.casefold() in q.casefold() for n in [c.domain, *brand_names(c)]) for q in self.queries
                       for c in direct)
        visited = any(p.startswith(tuple(c.name for c in direct)) for p in self.places)
        homepage = bool(self.result.signatures) and self.result.signatures[0].kind == "homepage"
        self.result.disqualifier_check_completed = homepage and bool(self.result.checked_places) and \
            (not direct or searched or visited)

    def run(self) -> CompanyResult:
        started = time.monotonic()
        try:
            try:
                self.home = self.ctx.fetcher(self.company.url, self.company.domain)
            except FetchError as exc:
                self.result.blocked.append(f"{self.company.url}: {exc}")
                self.result.error = "The homepage could not be read"
                return self.result
            finally:
                self.result.fetches += 1
                self.ctx.calls.meter.fetched()
            self.pages[self.home.url] = self.home
            self.names = company_names(self.company.domain, self.home)
            if len(self.company.name) >= 4 and self.company.name not in self.names and "." not in self.company.name:
                self.names.append(self.company.name)
            self.observe(self.home)
            if not self.result.name:
                self.result.name = self.names[-1] if self.names else self.company.domain
            try:
                answer = self.loop()
            except BudgetReached:
                self.result.status = "budget_reached"
                self.ctx.emit("investigation", "Stopped: run budget reached", company=self.company.domain, level="warn")
                return self.result
            except (AgentOutputError, AgentProviderError) as exc:
                self.result.error = str(exc)[:300]
                self.ctx.emit("investigation", f"Investigation incomplete: {exc}", company=self.company.domain,
                              level="warn")
                return self.result
            if answer.company_name.strip():
                self.result.name = answer.company_name.strip()[:200]
            self.keep(answer)
            return self.result
        finally:
            self.checked()
            if self.result.status == "investigating":
                self.result.status = "done"
            self.result.latency_ms = int((time.monotonic() - started) * 1000)
