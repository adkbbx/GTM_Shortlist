"""LABELLED SYNTHETIC TEST WORLD. Invented companies on reserved .example domains, scripted model answers and an
offline page fetcher. It makes no network or provider calls and exists for tests, the CLI demo (--synthetic) and
browser checks. Nothing here is a real company, page, quote or buying signal.

The scripted investigator answers through the same parsed shapes as the real Meta client (ModelTurn with function
calls and web_search calls), so the real agent loop, grounding, skeptic step and verdict code all run unchanged.
One answer deliberately quotes words that are not on the page, to show the grounding check dropping it.
"""
import json
import re
import time
from datetime import UTC, date, datetime, timedelta

from shortlist.agent.competitors import CLASSIFY_INSTRUCTIONS, SEARCH_INSTRUCTIONS
from shortlist.agent.discovery import DISCOVERY_INSTRUCTIONS
from shortlist.agent.investigation import INSTRUCTIONS as INVESTIGATE_INSTRUCTIONS
from shortlist.agent.pages import Page, page_from_document
from shortlist.agent.pipeline import Providers
from shortlist.agent.providers import ChatTurn, FunctionCall, ModelTurn, SearchCall, SearchResult
from shortlist.agent.seller import SELLER_INSTRUCTIONS
from shortlist.agent.telemetry import Pricing
from shortlist.fetch import FetchError, canonical_url, domain_of

LABEL = "SYNTHETIC TEST"
SELLER = "https://seller.example/"
VAGUE = "https://vague.example/"


def _html(title: str, body: str, head: str = "") -> bytes:
    return (f"<!doctype html><html><head><title>{title}</title>{head}</head><body>{body}</body></html>").encode()


def build_pages(today: date) -> dict[str, bytes]:
    posted = (today - timedelta(days=21)).isoformat()
    job_ld = json.dumps({"@context": "https://schema.org", "@type": "JobPosting", "title": "Customer Support Agent",
                         "datePosted": posted})
    return {
        SELLER: _html("Northwind Desk (synthetic test seller)", """
<nav><a href="/pricing">Pricing</a> <a href="/features">Features</a> <a href="/customers">Customers</a>
<a href="/about">About</a> <a href="/integrations">Integrations</a> <a href="/vs/rival-desk">Northwind vs RivalDesk</a></nav>
<h1>SYNTHETIC TEST SITE. Northwind Desk is help desk software for online stores.</h1>
<p>Answer every customer email and chat from one shared inbox.</p>
<p>Built for customer support teams at online retailers.</p>
<p>Replace shared Gmail inboxes and spreadsheets with real ticketing.</p>"""),
        "https://seller.example/pricing": _html("Pricing (synthetic)", """
<h1>SYNTHETIC TEST SITE. Pricing</h1><p>Plans start at 5 support agents.</p>
<p>Northwind Desk serves online retailers in North America and Europe.</p>"""),
        "https://seller.example/features": _html("Features (synthetic)", """
<h1>SYNTHETIC TEST SITE. Features</h1><p>Route customer emails and chats to the right agent automatically.</p>
<p>Opening a new store? Add it to Northwind Desk in one click.</p>"""),
        "https://seller.example/customers": _html("Customers (synthetic)", """
<h1>SYNTHETIC TEST SITE. Customers</h1><p>Acme Outdoor answers 3,000 customer emails a week with Northwind Desk.</p>
<img src="/logos/acme.png" alt="Acme Outdoor logo">"""),
        "https://seller.example/integrations": _html("Integrations (synthetic)", """
<h1>SYNTHETIC TEST SITE. Integrations</h1><p>Connect Shopify and WooCommerce stores in one click.</p>"""),
        "https://seller.example/vs/rival-desk": _html("Northwind Desk vs RivalDesk (synthetic)", """
<h1>SYNTHETIC TEST SITE. Northwind Desk vs RivalDesk</h1>
<p>Both are help desks for online stores. Northwind Desk adds chat at no extra cost.</p>"""),
        "https://seller.example/about": _html("About (synthetic)", """
<h1>SYNTHETIC TEST SITE. About Northwind Desk</h1><p>We help small online shops give great support.</p>"""),
        # Competitor candidates.
        "https://rival-desk.example/": _html("RivalDesk (synthetic)", """
<h1>SYNTHETIC TEST SITE. RivalDesk is help desk software for online retailers.</h1>
<p>Support teams at online stores use RivalDesk to answer every email and chat.</p>
<a href="/customers">Customers</a>"""),
        "https://rival-desk.example/customers": _html("RivalDesk customers (synthetic)", """
<h1>SYNTHETIC TEST SITE. Customer stories</h1>
<p>Bright Kettle answers every support chat in RivalDesk.</p>
<p>Many online stores trust RivalDesk every day.</p>"""),
        "https://chatwidget.example/": _html("ChatWidget (synthetic)", """
<h1>SYNTHETIC TEST SITE. ChatWidget adds a live chat bubble to any website.</h1>
<p>Loved by bloggers, schools and local clubs.</p>"""),
        "https://metricsboard.example/": _html("MetricsBoard (synthetic)", """
<h1>SYNTHETIC TEST SITE. MetricsBoard turns warehouse data into dashboards.</h1>
<p>Made for finance teams at large banks.</p>"""),
        # Companies.
        "https://trailgear.example/": _html("Trailgear Outfitters (synthetic)", """
<nav><a href="/careers/customer-support-agent">Careers</a> <a href="/about">About</a></nav>
<h1>SYNTHETIC TEST COMPANY. Trailgear Outfitters sells hiking gear through our online store.</h1>
<p>Questions? Email our support team or start a chat, seven days a week.</p>
<p>We ship to Canada, the United States and Mexico.</p>"""),
        "https://trailgear.example/careers/customer-support-agent": _html(
            "Customer Support Agent at Trailgear (synthetic job post)", """
<h1>SYNTHETIC TEST JOB POST. Customer Support Agent</h1>
<p>We are hiring two customer support agents to answer customer emails and chats from our shared Gmail inbox.</p>""",
            head=f'<script type="application/ld+json">{job_ld}</script>'),
        "https://trailgear.example/about": _html("About Trailgear (synthetic)", """
<h1>SYNTHETIC TEST COMPANY. About Trailgear Outfitters</h1><p>Trailgear Outfitters has sold hiking gear online since 2015.</p>"""),
        "https://oakandpine.example/": _html("Oak and Pine (synthetic)", """
<nav><a href="/about">About</a></nav>
<h1>SYNTHETIC TEST COMPANY. Oak and Pine sells handmade furniture through our online store.</h1>
<p>Email our support team any time and we reply within a day.</p>
<p>Oak and Pine integrates with RivalDesk for order notifications.</p>
<p>We are growing fast and our inbox is busier than ever.</p>"""),
        "https://oakandpine.example/about": _html("About Oak and Pine (synthetic)", """
<h1>SYNTHETIC TEST COMPANY. About Oak and Pine</h1><p>Oak and Pine was founded in Portland, Oregon.</p>"""),
        "https://brightkettle.example/": _html("Bright Kettle Tea (synthetic)", """
<h1>SYNTHETIC TEST COMPANY. Bright Kettle sells specialty tea through our online store.</h1>
<p>Chat with our support team or send us an email from any page.</p>
<script src="https://widget.rival-desk.example/embed.js"></script>
<footer><p>Customer support powered by RivalDesk</p></footer>"""),
        "https://acme-outdoor.example/": _html("Acme Outdoor (synthetic)", """
<h1>SYNTHETIC TEST COMPANY. Acme Outdoor sells camping gear online.</h1><p>Email us any time.</p>"""),
        "https://best-helpdesk-list.example/blog/top-10-help-desks": _html("Top 10 help desks for 2026 (synthetic)", """
<h1>SYNTHETIC TEST ARTICLE. Top 10 help desks</h1><p>A list article about help desk tools.</p>"""),
        VAGUE: _html("Vague Co (synthetic)", """
<h1>SYNTHETIC TEST SITE. We help teams do more with less.</h1>
<p>Smarter workflows for growing businesses.</p><p>Talk to our experts about automation and reporting.</p>"""),
    }


class SyntheticWeb:
    """Offline fetcher over the synthetic pages, with the same URL checks as the real fetcher."""

    def __init__(self, today: date):
        self.pages = build_pages(today)
        self.retrieved = datetime.combine(today, datetime.min.time(), tzinfo=UTC) + timedelta(hours=9)
        self.requests: list[str] = []

    def __call__(self, url: str, expected_domain: str | None = None) -> Page:
        current = canonical_url(url)
        self.requests.append(current)
        if expected_domain and domain_of(current) != expected_domain:
            raise FetchError("Redirect changed company identity; manual verification required")
        body = self.pages.get(current) or self.pages.get(current.rstrip("/"))
        if body is None:
            raise FetchError("Website returned HTTP 404")
        page = page_from_document(current, body, expected_domain)
        return Page(source=page.source.model_copy(update={"retrieved_at": self.retrieved}), html=page.html,
                    full_text=page.full_text, dates=page.dates, links=page.links)


def _quote(text: str, url: str) -> dict:
    return {"quote": text, "url": url}


SELLER_ANSWER = {
    "name": "Northwind Desk",
    "offer": {"value": "Help desk software for online stores",
              "quotes": [_quote("Northwind Desk is help desk software for online stores.", SELLER)]},
    "buyer": {"value": "Customer support teams at online retailers",
              "quotes": [_quote("Built for customer support teams at online retailers.", SELLER)]},
    "existing_customers": [{"name": "Acme Outdoor", "domain": "acme-outdoor.example", "quotes": [
        _quote("Acme Outdoor answers 3,000 customer emails a week with Northwind Desk.", "https://seller.example/customers")]}],
    "fit_criteria": [
        {"id": "fit-1", "text": "Sells products online through its own store", "required": True,
         "quotes": [_quote("help desk software for online stores", SELLER)]},
        {"id": "fit-2", "text": "Offers customer support by email or chat", "required": True,
         "quotes": [_quote("Answer every customer email and chat from one shared inbox.", SELLER)]},
        {"id": "fit-3", "text": "Ships orders to more than one country", "required": False,
         "quotes": [_quote("Northwind Desk serves online retailers in North America and Europe.",
                           "https://seller.example/pricing")]}],
    "need_signals": [
        {"id": "need-1", "text": "Hiring customer support agents", "quotes": [
            _quote("Built for customer support teams at online retailers.", SELLER),
            # Deliberately not on the page: the grounding check drops this quote and logs it.
            _quote("Teams cut first response times by 80 percent.", SELLER)]},
        {"id": "need-2", "text": "Answers support from a shared email inbox or spreadsheets", "quotes": [
            _quote("Replace shared Gmail inboxes and spreadsheets with real ticketing.", SELLER)]}],
    "timing_signals": [{"id": "timing-1", "text": "Recently opened a new store or product line", "quotes": [
        _quote("Opening a new store? Add it to Northwind Desk in one click.", "https://seller.example/features")]}],
    "stated_limits": [{"kind": "region", "value": "North America and Europe", "quotes": [
        _quote("Northwind Desk serves online retailers in North America and Europe.", "https://seller.example/pricing")]}],
    "interpretations": [],
}

VAGUE_ANSWER = {
    "name": "Vague Co", "offer": None, "buyer": None, "fit_criteria": [], "need_signals": [], "timing_signals": [],
    "interpretations": [
        {"offer": "Workflow automation software", "buyer": "Operations teams at growing businesses",
         "quotes": [_quote("Smarter workflows for growing businesses.", VAGUE)]},
        {"offer": "Automation and reporting consulting", "buyer": "Small business owners",
         "quotes": [_quote("Talk to our experts about automation and reporting.", VAGUE)]},
        {"offer": "Productivity coaching", "buyer": "Teams",
         # Not on the page: this reading is dropped, leaving two clickable ones.
         "quotes": [_quote("Coaching programs for productive teams.", VAGUE)]}]}

VAGUE_CHOSEN = {
    "name": "Vague Co",
    "offer": {"value": "Workflow automation software", "quotes": [_quote("Smarter workflows for growing businesses.", VAGUE)]},
    "buyer": {"value": "Operations teams at growing businesses",
              "quotes": [_quote("Smarter workflows for growing businesses.", VAGUE)]},
    "fit_criteria": [{"id": "fit-1", "text": "Runs operations with manual workflows", "required": True,
                      "quotes": [_quote("We help teams do more with less.", VAGUE)]}],
    "need_signals": [{"id": "need-1", "text": "Hiring operations staff", "quotes": [
        _quote("Talk to our experts about automation and reporting.", VAGUE)]}],
    "timing_signals": [], "existing_customers": [], "stated_limits": [], "interpretations": []}

COMPETITOR_ANSWER = {"candidates": [
    {"name": "RivalDesk", "domain": "rival-desk.example", "url": "https://rival-desk.example/", "found_via": "Northwind Desk alternatives"},
    {"name": "ChatWidget", "domain": "chatwidget.example", "url": "https://chatwidget.example/", "found_via": "Northwind Desk vs"},
    {"name": "MetricsBoard", "domain": "metricsboard.example", "url": "https://metricsboard.example/", "found_via": "help desk software"},
    {"name": "Help desk reviews", "domain": "g2.com", "url": "https://www.g2.com/categories/help-desk", "found_via": "reviews"}]}

CLASSIFY_ANSWER = {"competitors": [
    {"domain": "rival-desk.example", "name": "RivalDesk", "classification": "direct",
     "same_job_quote": "RivalDesk is help desk software for online retailers.",
     "same_buyer_quote": "Support teams at online stores use RivalDesk to answer every email and chat.",
     "reason": "Same help desk product for the same online store support teams."},
    {"domain": "chatwidget.example", "name": "ChatWidget", "classification": "direct",
     "same_job_quote": "ChatWidget adds a live chat bubble to any website.",
     # Not on the page: the direct claim is downgraded to adjacent.
     "same_buyer_quote": "Built for support teams at online stores.",
     "reason": "Live chat for websites."},
    {"domain": "metricsboard.example", "name": "MetricsBoard", "classification": "not_competitor",
     "same_job_quote": None, "same_buyer_quote": None, "reason": "Dashboards for finance teams."}]}

DISCOVERY_ANSWER = {"companies": [
    {"name": "Trailgear Outfitters", "domain": "trailgear.example", "url": "https://trailgear.example/",
     "found_via": "online stores with email and chat support"},
    {"name": "Oak and Pine", "domain": "oakandpine.example", "url": "https://oakandpine.example/",
     "found_via": "similar to Acme Outdoor"},
    {"name": "Bright Kettle", "domain": "brightkettle.example", "url": "https://brightkettle.example/",
     "found_via": "online stores with email and chat support"},
    {"name": "Acme Outdoor", "domain": "acme-outdoor.example", "url": "https://acme-outdoor.example/", "found_via": "camping"},
    {"name": "RivalDesk", "domain": "rival-desk.example", "url": "https://rival-desk.example/", "found_via": "help desk"},
    {"name": "Northwind Desk", "domain": "seller.example", "url": SELLER, "found_via": "help desk"}]}

DISCOVERY_SEARCH = SearchCall(query="online stores customer support email chat", results=(
    SearchResult(title="Top 10 help desks for 2026", url="https://best-helpdesk-list.example/blog/top-10-help-desks",
                 snippet="SYNTHETIC list article"),
    SearchResult(title="Trailgear Outfitters", url="https://trailgear.example/", snippet="SYNTHETIC hiking gear store"),
    SearchResult(title="Help desk software reviews", url="https://www.g2.com/categories/help-desk", snippet="SYNTHETIC")))


def investigation_plan(today: date) -> dict[str, dict]:
    posted = (today - timedelta(days=21)).isoformat()
    home = "https://{}/"
    return {
        "trailgear.example": {
            "fetch": ["https://trailgear.example/careers/customer-support-agent"],
            "search": SearchCall(query="Trailgear Outfitters RivalDesk", results=()),
            "evidence": [
                {"claim_type": "fit", "criterion_id": "fit-1", "claim": "Sells hiking gear through its own online store",
                 "quote": "Trailgear Outfitters sells hiking gear through our online store.", "url": home.format("trailgear.example"),
                 "source_type": "own_site", "published_date": None},
                {"claim_type": "fit", "criterion_id": "fit-2", "claim": "Offers support by email and chat",
                 "quote": "Questions? Email our support team or start a chat, seven days a week.",
                 "url": home.format("trailgear.example"), "source_type": "own_site", "published_date": None},
                {"claim_type": "need", "criterion_id": "need-1", "claim": "Hiring two customer support agents",
                 "quote": "We are hiring two customer support agents to answer customer emails and chats from our shared Gmail inbox.",
                 "url": "https://trailgear.example/careers/customer-support-agent", "source_type": "job_post",
                 "published_date": posted},
                # Deliberately not on the page: dropped by the grounding check and logged.
                {"claim_type": "fit", "criterion_id": "fit-3", "claim": "Ships worldwide",
                 "quote": "We ship to 40 countries worldwide.", "url": home.format("trailgear.example"),
                 "source_type": "own_site", "published_date": None}]},
        "oakandpine.example": {
            "fetch": ["https://oakandpine.example/about"],
            "search": SearchCall(query="Oak and Pine RivalDesk", results=(
                SearchResult(title="Oak and Pine", url="https://oakandpine.example/",
                             snippet="SYNTHETIC Oak and Pine integrates with RivalDesk for order notifications."),)),
            "evidence": [
                {"claim_type": "fit", "criterion_id": "fit-1", "claim": "Sells furniture through its own online store",
                 "quote": "Oak and Pine sells handmade furniture through our online store.",
                 "url": home.format("oakandpine.example"), "source_type": "own_site", "published_date": None},
                {"claim_type": "fit", "criterion_id": "fit-2", "claim": "Offers email support",
                 "quote": "Email our support team any time and we reply within a day.",
                 "url": home.format("oakandpine.example"), "source_type": "own_site", "published_date": None},
                {"claim_type": "need", "criterion_id": "need-2", "claim": "Its support inbox is getting busier",
                 "quote": "We are growing fast and our inbox is busier than ever.",
                 "url": home.format("oakandpine.example"), "source_type": "own_site", "published_date": None},
                {"claim_type": "disqualifier", "criterion_id": "uses_direct_competitor:rival-desk.example",
                 "claim": "Integrates with RivalDesk", "quote": "Oak and Pine integrates with RivalDesk for order notifications.",
                 "url": home.format("oakandpine.example"), "source_type": "own_site", "published_date": None}]},
        "brightkettle.example": {
            "fetch": ["https://rival-desk.example/customers"],
            "search": SearchCall(query="Bright Kettle RivalDesk", results=(
                SearchResult(title="RivalDesk customer stories", url="https://rival-desk.example/customers",
                             snippet="SYNTHETIC Bright Kettle answers every support chat in RivalDesk."),)),
            "evidence": [
                {"claim_type": "fit", "criterion_id": "fit-1", "claim": "Sells tea through its own online store",
                 "quote": "Bright Kettle sells specialty tea through our online store.",
                 "url": home.format("brightkettle.example"), "source_type": "own_site", "published_date": None},
                {"claim_type": "fit", "criterion_id": "fit-2", "claim": "Offers chat and email support",
                 "quote": "Chat with our support team or send us an email from any page.",
                 "url": home.format("brightkettle.example"), "source_type": "own_site", "published_date": None},
                {"claim_type": "disqualifier", "criterion_id": "uses_direct_competitor:rival-desk.example",
                 "claim": "RivalDesk names Bright Kettle as a current customer",
                 "quote": "Bright Kettle answers every support chat in RivalDesk.",
                 "url": "https://rival-desk.example/customers", "source_type": "competitor_site", "published_date": None}]},
    }


def _tokens(*parts) -> int:
    return max(1, sum(len(json.dumps(part)) if not isinstance(part, str) else len(part) for part in parts) // 4)


class SyntheticInvestigator:
    """Scripted stand-in for Muse Spark on the Meta Model API. LABELLED SYNTHETIC."""
    provider = "synthetic-meta"
    model = "synthetic-muse-spark"
    continuation = "replay"

    def __init__(self, today: date, pace: float = 0.0):
        self.pricing = Pricing(1.25, 4.25, 2.50 / 1000)
        self.plan = investigation_plan(today)
        self.pace = pace
        self.requests: list[dict] = []

    def respond(self, *, instructions, input, tools, previous_response_id=None, max_output_tokens=4000) -> ModelTurn:
        if self.pace:
            time.sleep(self.pace)
        self.requests.append({"instructions": instructions[:60], "tools": [t.get("type") for t in tools]})
        first = input[0].get("content", "") if input and isinstance(input[0], dict) else ""
        searches: tuple[SearchCall, ...] = ()
        calls: tuple[FunctionCall, ...] = ()
        if first.startswith("Your previous answer was not valid JSON"):
            text = re.search(r"<data>\n(.*)\n</data>", first, re.DOTALL).group(1)
            answer = text.strip().strip("`")
        elif instructions == SELLER_INSTRUCTIONS:
            if "vague.example" in first:
                answer = json.dumps(VAGUE_CHOSEN if "chose this reading" in first else VAGUE_ANSWER)
            else:
                answer = json.dumps(SELLER_ANSWER)
        elif instructions == SEARCH_INSTRUCTIONS:
            searches = (SearchCall(query="Northwind Desk alternatives", results=tuple(
                SearchResult(title=c["name"], url=c["url"], snippet="SYNTHETIC") for c in COMPETITOR_ANSWER["candidates"])),)
            answer = json.dumps(COMPETITOR_ANSWER)
        elif instructions == CLASSIFY_INSTRUCTIONS:
            answer = json.dumps(CLASSIFY_ANSWER)
        elif instructions == DISCOVERY_INSTRUCTIONS:
            searches = (DISCOVERY_SEARCH,)
            answer = json.dumps(DISCOVERY_ANSWER)
        elif instructions == INVESTIGATE_INSTRUCTIONS:
            company = re.search(r'"company": "([^"]+)"', first)
            plan = self.plan.get(company.group(1) if company else "", {})
            answered = any(isinstance(item, dict) and item.get("type") == "function_call_output" for item in input)
            if plan and not answered and tools:
                searches = (plan["search"],)
                calls = tuple(FunctionCall(call_id=f"call-{index}", name="fetch_page", arguments=json.dumps({"url": url}))
                              for index, url in enumerate(plan["fetch"]))
                answer = ""
            else:
                answer = json.dumps({"company_name": "", "evidence": plan.get("evidence", [])})
        else:
            answer = "{}"
        items = [{"type": "web_search_call", "status": "completed", "action": {"type": "search", "query": s.query}}
                 for s in searches]
        items += [{"type": "function_call", "call_id": c.call_id, "name": c.name, "arguments": c.arguments} for c in calls]
        if answer:
            items.append({"type": "message", "role": "assistant", "content": [{"type": "output_text", "text": answer}]})
        return ModelTurn(text=answer, function_calls=calls, searches=searches, output_items=items,
                         response_id=f"synthetic-{len(self.requests)}", input_tokens=_tokens(instructions, input),
                         output_tokens=_tokens(answer or "call"), latency_ms=int(self.pace * 1000) or 1)


class SyntheticSkeptic:
    """Scripted stand-in for Muse Spark Open on Baseten. It applies the skeptic's written rules to each quote.
    LABELLED SYNTHETIC."""
    provider = "synthetic-baseten"
    model = "synthetic-muse-spark-open-1026"

    def __init__(self, pace: float = 0.0):
        self.pricing = Pricing(1.25, 4.25)
        self.pace = pace
        self.requests: list[list[dict]] = []

    def chat(self, messages, *, max_tokens=2000) -> ChatTurn:
        if self.pace:
            time.sleep(self.pace)
        self.requests.append(messages)
        data = json.loads(re.search(r"<data>\n(.*)\n</data>", messages[-1]["content"], re.DOTALL).group(1))
        decisions = []
        for item in data["items"]:
            quote = item["quote"]
            if item["claim_type"] == "need" and item["source_type"] == "own_site":
                decision, reason = "insufficient", "Own-site text cannot show need."
            elif item["claim_type"] == "disqualifier" and re.search(
                    r"integrat|\bvs\b|versus|alternative|compar|formerly|switched|used to", quote, re.IGNORECASE):
                decision, reason = "insufficient", "Mentions an integration or comparison, not current use."
            else:
                decision, reason = "supports", "The quote states this directly."
            decisions.append({"id": item["id"], "decision": decision, "reason": reason})
        text = json.dumps({"decisions": decisions})
        return ChatTurn(text=text, input_tokens=_tokens(messages), output_tokens=_tokens(text),
                        latency_ms=int(self.pace * 1000) or 1)


def synthetic_providers(today: date | None = None, pace: float = 0.0) -> Providers:
    today = today or datetime.now(UTC).date()
    web = SyntheticWeb(today)
    clock_base = datetime.combine(today, datetime.min.time(), tzinfo=UTC) + timedelta(hours=10)
    started = time.monotonic()

    def clock():
        return clock_base + timedelta(seconds=time.monotonic() - started)

    return Providers(investigator=SyntheticInvestigator(today, pace), skeptic=SyntheticSkeptic(pace), fetcher=web,
                     synthetic=True, clock=clock)
