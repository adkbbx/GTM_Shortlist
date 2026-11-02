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
from shortlist.agent.jobboards import MAX_OPENINGS, Board, JobBoards, board_refs, posting_page
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
    own_role_page,
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
from shortlist.relevance import CLIENT_ROLE, service_business, staffing_firm

MAX_SEARCHES = 4
MAX_FETCHES = 6
MAX_TURNS = 8
# Before any model call: the run researches the next candidate instead (pipeline.AgentRunner.research).
HOMEPAGE_UNREADABLE = "The homepage could not be read"

INSTRUCTIONS = f"""You investigate ONE company for a B2B seller and collect quoted evidence. {UNTRUSTED}

Work in this order:
1. Fit: check each fit check against the company's own pages. The homepage text is supplied; call fetch_page for
   other pages on its site (product, pricing, about, careers).
2. Need and timing (spend most of your searches here): the company's own marketing cannot show need, so look
   beyond it. The exception is a need signal with own_site: true, a fact the company publishes about itself (a trust
   or security page, compliance work it lists): fetch that page on its site and quote it. Search for its job posts (its careers page, or job boards such as Greenhouse, Lever, Workable or
   LinkedIn) for roles named in the need signals, and for news or press releases from the last six months for the
   timing signals. open_posting, when present, is a job posting confirmed open just now and its text is supplied:
   quote its own sentences for the need signals it shows, with that url, before searching for more. lead_page, when
   present, is the news article or post where this company was found, and its text is supplied: quote it for the
   timing or need signal it shows, with its url and the date the page states. own_job_board,
   when present, lists the company's open roles read just now from its own job board: if a role there matches a need
   signal, fetch that role's url and quote it, because it beats a copy on a
   job site. If found_via names a job post or news item, find and fetch that page first. Fetch the job post or
   article itself and quote it. Note a page's publication date only when the page states it.
3. Competitor use: ONE search that names all listed competitors together, for example
   "<company> <competitor 1> <competitor 2>"; the company's own page code is already scanned for them. Fetch a
   competitor's customer or case-study page only if a result names the company. Evidence must show CURRENT use, not
   an integration, a comparison article or past use.
4. Size: if a disqualifier check is about size or stage, quote the company's own words about its team size, headcount
   or funding stage (about, team or careers page, or a funding announcement), using that check's id with claim_type
   "disqualifier", whether the words show it is within the size or outside it. The reviewer decides which.
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
    job_boards: JobBoards | None = None

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


# discovery.lead's wording for a posting it confirmed open on the company's own board, ending with the posting's url.
LEAD_POSTING = re.compile(r"^open job post on its \w+ board: .*\((https://[^()\s]+)\)$")


class Investigation:
    def __init__(self, company: CandidateRef, ctx: Context):
        self.company = company
        self.ctx = ctx
        self.result = CompanyResult(domain=company.domain, name=company.name, url=company.url,
                                    found_via=company.found_via, signal=company.signal, status="investigating")
        self.pages: dict[str, Page] = {}
        self.places: list[str] = []
        self.queries: list[str] = []
        self.home: Page | None = None
        self.names: list[str] = []
        self.board: Board | None = None
        self.posting: Page | None = None
        self.source: Page | None = None

    # Pages -----------------------------------------------------------------------------------------------------
    def works_for_others(self) -> bool:
        """A recruiting firm, staffing firm or agency in its own homepage's words, when the seller sells to product
        companies: its hiring is for clients and it is not a buyer. Found with no model call; the skeptic still judges
        the quote, and the paid research is skipped."""
        rule = next((r for r in self.ctx.rules if r.enabled and r.rule == "works_for_others"), None)
        if rule is None or self.home is None:
            return False
        for line in [self.home.source.title, *self.home.source.text.splitlines()[:15]]:
            line = line.strip()
            if not 12 <= len(line) <= 300 or not (staffing_firm(line) or service_business(line)):
                continue
            located = ground(line, self.home)
            if located is None:
                continue
            text, location = located
            self.result.evidence.append(EvidenceItem(
                claim_type="disqualifier", criterion_id=rule.id, claim=rule.text, found_by="scan",
                quote=Quote(text=text, url=self.home.url, source_type="own_site", fetched_at=self.home.fetched_at,
                            location=location)))
            self.ctx.emit("investigation", f"Its homepage describes a recruiting firm, staffing firm or agency: "
                                           f"“{text[:100]}”; skipping deeper research", company=self.company.domain)
            return True
        return False

    def read_lead_source(self):
        """The news article or post discovery saw the company's signal on, read first and handed to the investigator.
        A live run found mintive.com by its seed round and launch, then quoted only the company's own pages, which
        cannot show need. LinkedIn is never fetched: its terms forbid automated access."""
        url = self.company.source_url
        if not url or self.posting is not None or re.search(r"(?:^|\.)linkedin\.com$", urlsplit(url).hostname or ""):
            return
        try:
            page = self.fetch(url)
        except FetchError as exc:
            self.result.blocked.append(f"{url[:300]}: {exc}")
            return
        self.source = page
        self.ctx.emit("investigation", f"Read where it was found: {url[:120]}", company=self.company.domain)

    def read_lead_posting(self):
        """The posting discovery confirmed open, read from its board's own data (no model call) and handed to the
        investigator. Live runs found an open, dated posting and still ended "No current need": the investigator
        quoted the board page's heading instead (rescale.com) or never fetched the posting."""
        match = LEAD_POSTING.search(self.company.found_via or "")
        if match is None or self.ctx.job_boards is None:
            return
        page = self.ctx.job_boards.page_for(match.group(1))
        if page is None:
            return
        self.posting = self.pages[page.url] = page
        self.places.append("job post")
        self.ctx.emit("investigation", f"Read the open posting: {page.source.title[:120]}", company=self.company.domain)

    def fetch(self, url: str) -> Page:
        if self.result.fetches >= MAX_FETCHES:
            raise FetchError("Fetch limit for this company reached")
        self.result.fetches += 1
        self.ctx.calls.meter.fetched()
        expected = self.company.domain if domain_of(url) == self.company.domain else None
        try:
            page = self.ctx.fetcher(url, expected)
        except FetchError:
            listed = self.ctx.job_boards.page_for(url) if self.ctx.job_boards is not None and board_refs(url) else None
            if listed is None:
                raise
            page = listed
            self.ctx.emit("investigation", f"Read the posting from its job board's list: {url[:120]}",
                          company=self.company.domain)
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
            page = self.fetch(posting_page(url))
        except FetchError as exc:
            if "limit" not in str(exc):
                self.result.blocked.append(f"{url[:300]}: {exc}")
                self.ctx.emit("investigation", f"Could not read {url[:160]}", company=self.company.domain, level="warn")
            return f"Could not fetch this page: {exc}"
        self.ctx.emit("investigation", f"Read {page.url[:200]}", company=self.company.domain)
        dates = ", ".join(d.isoformat() for d in page.dates[:3])
        note = f"\nThe page declares publication date(s): {dates}" if dates else ""
        return f'<page url="{page.url}">\n{excerpt(page, 6000)}\n</page>{note}'

    def read_board(self):
        """The company's own job board, found from its own site (no model call)."""
        if self.ctx.job_boards is None or self.home is None:
            return
        self.board = self.ctx.job_boards.own(self.home, self.fetch)
        if self.board is not None:
            self.places.append(f"own job board on {self.board.label}")
            self.ctx.emit("investigation", f"Read its own job board on {self.board.label}: "
                          f"{len(self.board.openings)} open role{'' if len(self.board.openings) == 1 else 's'}",
                          company=self.company.domain)

    # Loop ------------------------------------------------------------------------------------------------------
    def brief(self) -> str:
        profile = self.ctx.profile
        data = {
            "company": self.company.domain, "homepage": self.home.url if self.home else self.company.url,
            "seller_offer": profile.offer.value if profile.offer else "",
            "seller_buyer": profile.buyer.value if profile.buyer else "",
            "fit_checks": [{"id": c.id, "text": c.text, "required": c.required} for c in profile.fit_criteria if c.enabled],
            "need_signals": [{"id": s.id, "text": s.text, "own_site": s.own_site} for s in profile.need_signals],
            "timing_signals": [{"id": s.id, "text": s.text} for s in profile.timing_signals],
            "disqualifier_checks": [{"id": r.id, "text": r.text} for r in self.ctx.rules
                                    if r.enabled and r.rule not in ("is_competitor", "is_existing_customer")],
            "competitors": [{"name": c.name, "domain": c.domain} for c in self.ctx.direct],
            # Discovery's lead (a job post or news item it saw); a lead to check, never evidence by itself.
            "found_via": self.company.found_via or "",
        }
        if self.board is not None:
            data["own_job_board"] = {"url": self.board.url, "open_roles": [
                {"title": o.title, "location": o.location, "url": o.url,
                 "posted": o.posted.isoformat() if o.posted else None} for o in self.board.openings[:MAX_OPENINGS]]}
        home = f'\n<page url="{self.home.url}">\n{excerpt(self.home, 6000)}\n</page>' if self.home else ""
        if self.posting is not None:
            data["open_posting"] = self.posting.url
            home += f'\n<page url="{self.posting.url}">\n{excerpt(self.posting, 6000)}\n</page>'
        if self.source is not None:
            data["lead_page"] = self.source.url
            home += f'\n<page url="{self.source.url}">\n{excerpt(self.source, 6000)}\n</page>'
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
                    self.ctx.emit("investigation", f'Searched "{search.query[:160]}"', company=self.company.domain)
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
            if kind == "job_post" and item.claim_type in ("need", "timing") and CLIENT_ROLE.search(page.full_text):
                drop.append(DroppedClaim(stage="investigation", company=self.company.domain, claim_type=item.claim_type,
                                         quote=text[:1500], url=page.url,
                                         reason="The posting is for the poster's client, not for this company"))
                continue
            evidence = EvidenceItem(
                claim_type=item.claim_type, criterion_id=criterion, claim=(item.claim.strip() or text)[:600],
                quote=Quote(text=text, url=page.url, published_date=published, fetched_at=page.fetched_at,
                            source_type=kind, location=location,
                            open_posting=kind == "job_post" and (open_posting(page)
                                                                 or own_role_page(page, self.company.domain))))
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
                self.result.error = HOMEPAGE_UNREADABLE
                return self.result
            finally:
                self.result.fetches += 1
                self.ctx.calls.meter.fetched()
            self.pages[self.home.url] = self.home
            self.names = company_names(self.company.domain, self.home)
            if len(self.company.name) >= 4 and self.company.name not in self.names and "." not in self.company.name:
                self.names.append(self.company.name)
            self.observe(self.home)
            if self.works_for_others():
                return self.result
            self.read_board()
            self.read_lead_posting()
            self.read_lead_source()
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
