"""Sample data: try the whole research flow before adding search or model keys.

Every company, page, person and passage here is invented. Domains use the reserved .example names (RFC 2606), which
never resolve, so no real company is implied and nothing leaves this computer. A run flagged as a sample uses these
providers in place of search, page fetches and model calls, and every screen and export labels it as sample data.
"""
import hashlib
import math
import re
import time
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from urllib.parse import urlsplit

from shortlist.domain import Candidate, Criterion, Profile, Research, Source
from shortlist.fetch import FetchError, canonical_url, domain_of
from shortlist.providers import SellerDraft, validate_extraction
from shortlist.verification import Judgment, Verification, assessments

SAMPLE_SELLER_URL = "https://relay-studio.example/"
SAMPLE_PROVIDER = "sample_data"
PAGE_LABEL = "Sample data: an invented company page, not a real website."


@dataclass(frozen=True)
class Page:
    title: str
    # (sentence, claim): the claim is how a finding summarises the sentence; the sentence is the quoted passage.
    statements: tuple[tuple[str, str], ...]
    dated: bool = False


@dataclass(frozen=True)
class Company:
    name: str
    summary: str
    pages: dict[str, Page]
    facts: dict[str, tuple[str, str, str]] = field(default_factory=dict)  # kind: (page, sentence, claim)
    person: tuple[str, str, str, str] | None = None  # (page, name, role, sentence)


SELLER = Company("Relay Studio", "Onboarding reviews for B2B software teams", {"": Page("Relay Studio · Onboarding reviews", (
    ("Relay Studio reviews customer onboarding for B2B software teams.", ""),
    (("We map the path from signup to first value, find where new accounts stall and redesign the handover from sales "
      "to customer success."), ""),
    ("Each review takes four weeks and ends with a written onboarding plan.", ""),
))})

COMPETITORS = {
    "signalhouse.example": Company("Signalhouse", "Onboarding reviews and activation audits for B2B software teams", {}),
    "pagelane.example": Company("Pagelane", "Product onboarding reviews and in-app guide design for B2B software teams", {}),
    "quillstack.example": Company("Quillstack", "Customer onboarding reviews and training for B2B software companies", {}),
}

COMPANIES = {
    "northstar.example": Company(
        "Northstar Cloud", "Customer onboarding software for business teams",
        {"": Page("Northstar Cloud · Customer onboarding software", (
            ("Northstar Cloud sells customer onboarding software to business customers.",
             "Sells onboarding software to business customers"),
            ("Our guided onboarding moves each new customer from signup to activation in days.",
             "Runs a guided onboarding process from signup to activation"),
            ("Teams can start a free trial and invite colleagues without a sales call.",
             "Offers a free trial without a sales call"),
            ("We are hiring two customer success managers to support our growing customer team.",
             "Hiring customer success managers for a growing team"),
         )),
         "about": Page("About Northstar Cloud", (
            ("Northstar Cloud is headquartered in Toronto, Canada.", "Headquartered in Toronto, Canada"),
            ("Our team has 85 employees.", "85 employees, as stated on the sample page"),
            ("Sam Rivera is our Head of Customer Success.", "Sam Rivera leads customer success"),
         )),
         "news": Page("Northstar Cloud news", (
            ("Northstar Cloud launched onboarding analytics for account managers.", "Launched onboarding analytics"),
         ), dated=True)},
        facts={"description": ("", "Northstar Cloud sells customer onboarding software to business customers.",
                               "Customer onboarding software sold to business customers."),
               "location": ("about", "Northstar Cloud is headquartered in Toronto, Canada.", "Headquartered in Toronto, Canada."),
               "team_size": ("about", "Our team has 85 employees.", "85 employees, as stated on the sample page.")},
        person=("about", "Sam Rivera", "Head of Customer Success", "Sam Rivera is our Head of Customer Success."),
    ),
    "lumenly.example": Company(
        "Lumenly", "Project planning software for business teams",
        {"": Page("Lumenly · Project planning for business teams", (
            ("Lumenly is project planning software for business teams.", "Project planning software for business teams"),
            # Employee onboarding, not customer onboarding: the sample's required check stays unknown, as it should.
            ("Lumenly templates cover employee onboarding, product launches and quarterly planning.",
             "Templates for employee onboarding and planning"),
            ("Start a free trial and sign up your whole team in minutes.", "Offers a free trial with self-serve signup"),
         )),
         "about": Page("About Lumenly", (
            ("Lumenly is based in Lisbon, Portugal.", "Based in Lisbon, Portugal"),
         ))},
        facts={"description": ("", "Lumenly is project planning software for business teams.",
                               "Project planning software for business teams."),
               "location": ("about", "Lumenly is based in Lisbon, Portugal.", "Based in Lisbon, Portugal.")},
    ),
    "brightpath.example": Company(
        "Brightpath HR", "People operations software for growing companies",
        {"": Page("Brightpath HR · People operations software", (
            ("Brightpath HR sells people operations software to growing business customers.",
             "Sells people operations software to businesses"),
            ("HR teams use Brightpath to welcome new employees and collect their documents.",
             "Helps HR teams welcome new employees"),
         )),
         "about": Page("About Brightpath HR", (
            ("Brightpath HR has a team of 40 people.", "A team of 40, as stated on the sample page"),
         ))},
        facts={"description": ("", "Brightpath HR sells people operations software to growing business customers.",
                               "People operations software for growing businesses."),
               "team_size": ("about", "Brightpath HR has a team of 40 people.", "A team of 40, as stated on the sample page.")},
    ),
    "tidewater.example": Company(
        "Tidewater Labs", "Analytics software for subscription businesses",
        {"": Page("Tidewater Labs · Subscription analytics", (
            ("Tidewater Labs sells analytics software to subscription business customers.",
             "Sells analytics software to subscription businesses"),
            ("Our implementation team runs onboarding for every new customer account.",
             "Runs onboarding for each new customer account"),
         )),
         "about": Page("About Tidewater Labs", (
            ("We are hiring a customer success lead to grow our customer team.", "Hiring a customer success lead"),
         ))},
        facts={"description": ("", "Tidewater Labs sells analytics software to subscription business customers.",
                               "Analytics software for subscription businesses.")},
    ),
    "oakpoint.example": Company(
        "Oakpoint Systems", "Inventory software for wholesale distributors",
        {"": Page("Oakpoint Systems · Inventory software", (
            ("Oakpoint Systems is inventory software for wholesale business customers.",
             "Inventory software for wholesale businesses"),
            ("Our implementation team handles data migration and staff training for each customer.",
             "An implementation team handles migration and training"),
         )),
         "about": Page("About Oakpoint Systems", (
            ("Oakpoint Systems is headquartered in Leeds, United Kingdom.", "Headquartered in Leeds, United Kingdom"),
         ))},
        facts={"location": ("about", "Oakpoint Systems is headquartered in Leeds, United Kingdom.",
                            "Headquartered in Leeds, United Kingdom.")},
    ),
    "harbor-ops.example": Company(
        "Harbor Ops", "Operations software for field service businesses",
        {"": Page("Harbor Ops · Field service operations", (
            ("Harbor Ops is operations software for field service businesses.", "Operations software for field service"),
            ("Crews schedule jobs, track parts and send invoices from one mobile app.", "Scheduling, parts and invoicing"),
         )),
         "about": Page("About Harbor Ops", (
            ("Harbor Ops has 120 employees.", "120 employees, as stated on the sample page"),
         ))},
        facts={"team_size": ("about", "Harbor Ops has 120 employees.", "120 employees, as stated on the sample page.")},
    ),
}

STOP = frozenset({"that", "this", "with", "from", "into", "their", "they", "them", "have", "has", "such", "also",
                  "your", "ours", "what", "when", "which", "more", "most", "some", "than", "very", "each", "every"})
NEGATION = re.compile(r"\b(?:not|no|never|without|except|non|excluding)\b", re.IGNORECASE)


def words(text: str) -> set[str]:
    return {word.removesuffix("s") for word in re.findall(r"[a-z]+", text.casefold()) if len(word) > 3 and word not in STOP}


def match(check: str, statements: list[tuple[str, str, str]]) -> tuple[str, str, str] | None:
    """The sample statement sharing the most words with a check, or None. Deliberately literal: sample data never infers."""
    wanted = words(check)
    if not wanted or NEGATION.search(check):
        return None
    scored = sorted(((len(wanted & words(sentence)), index) for index, (_, sentence, _) in enumerate(statements)), reverse=True)
    score, index = scored[0] if scored else (0, 0)
    return statements[index] if score >= max(2, math.ceil(len(wanted) / 3)) else None


def page_of(url: str) -> tuple[Company, Page]:
    domain = domain_of(url)
    company = SELLER if domain == domain_of(SAMPLE_SELLER_URL) else COMPANIES.get(domain)
    page = company.pages.get(urlsplit(url).path.strip("/")) if company else None
    if page is None:
        raise FetchError("Sample data has no page at this address")
    return company, page


def page_text(page: Page) -> str:
    sentences = [sentence for sentence, _ in page.statements]
    if page.dated:
        sentences[0] = f"On {(datetime.now(UTC) - timedelta(days=3)).date().isoformat()}, " + sentences[0][0].lower() + sentences[0][1:]
    return " ".join([PAGE_LABEL, *sentences])


class SampleSearch:
    name = SAMPLE_PROVIDER

    def __init__(self, pace: float = 1.0):
        self.pace = pace

    def search(self, query: str, seller_url: str | None) -> list[Candidate]:
        time.sleep(.5 * self.pace)
        if seller_url is None:
            return []  # Sample runs start from the sample company's page; there is no company to look up.
        found = COMPETITORS if "similar companies official websites" in query else COMPANIES
        return [Candidate(domain=domain, name=company.name, url=f"https://{domain}/", query=query, provider=self.name,
                          excerpt="Sample data. " + company.summary + ".") for domain, company in found.items()]


def sample_fetch(pace: float = 1.0):
    def fetch(url: str, expected_domain: str | None = None) -> Source:
        time.sleep(.2 * pace)
        url = canonical_url(url)
        company, page = page_of(url)
        domain = domain_of(url)
        if expected_domain is not None and expected_domain != domain:
            raise FetchError("Sample page belongs to a different company")
        text = page_text(page)
        root = not urlsplit(url).path.strip("/")
        return Source(url=url, company_domain=domain, title=page.title, text=text,
                      content_hash=hashlib.sha256(text.encode()).hexdigest(),
                      research_links=(f"https://{domain}/about",) if root and "about" in company.pages else (),
                      activity_links=(f"https://{domain}/news",) if root and "news" in company.pages else ())
    return fetch


class SampleModel:
    name = SAMPLE_PROVIDER

    def __init__(self, pace: float = 1.0):
        self.pace = pace

    def seller(self, source: Source) -> SellerDraft:
        time.sleep(.6 * self.pace)
        return SellerDraft(
            offer="Onboarding reviews for B2B software teams: we map signup to first value and fix where new accounts stall",
            target="B2B software companies with a self-serve or sales-led customer onboarding process",
            criteria=[Criterion(id="business-software", description="Sells software to business customers"),
                      Criterion(id="onboarding", description="Describes a customer onboarding or activation process"),
                      Criterion(id="customer-team", description="Shows a growing customer success team, such as open roles",
                                required=False)],
            unknowns=[])

    def market(self, draft: SellerDraft, candidates: list[Candidate]):
        from shortlist.market import Campaign, CampaignPlan
        time.sleep(.6 * self.pace)
        rationale = "Sample hypothesis, not an observed market fact: "
        return CampaignPlan(campaigns=(
            Campaign(name="Self-serve trials", target="B2B software companies that offer a free trial or self-serve signup",
                     rationale=rationale + "self-serve products depend on onboarding to turn trials into customers.",
                     criteria=(Criterion(id="business-software", description="Sells software to business customers"),
                               Criterion(id="free-trial", description="Offers a free trial or self-serve signup")),
                     search_terms="B2B software free trial self-serve signup",
                     signals_to_check=("Hiring for customer success roles",)),
            Campaign(name="Implementation-led onboarding",
                     target="B2B software companies whose implementation team runs customer onboarding",
                     rationale=rationale + "teams that onboard by hand feel every stalled account.",
                     criteria=(Criterion(id="business-software", description="Sells software to business customers"),
                               Criterion(id="implementation", description="Has an implementation team that runs customer onboarding")),
                     search_terms="B2B software implementation team customer onboarding"),
            Campaign(name="Operations software", target="Operations and HR software companies selling to growing businesses",
                     rationale=rationale + "operations buyers expect a guided first month.",
                     criteria=(Criterion(id="operations-software", description="Sells operations or people operations software"),),
                     search_terms="operations software for growing businesses"),
        ))

    def research(self, profile: Profile, candidate: Candidate, sources: tuple[Source, ...]) -> Research:
        time.sleep(.6 * self.pace)
        company = COMPANIES.get(candidate.domain)
        if company is None:
            raise FetchError("Sample data has no company at this address")
        located = {urlsplit(source.url).path.strip("/"): source for source in sources}
        statements = [(located[path].id, sentence, claim) for path, page in company.pages.items() if path in located
                      for sentence, claim in page.statements if not page.dated]
        missing = "Sample data: no sample passage addresses this check."
        findings = []
        for criterion in profile.criteria:
            found = match(criterion.description, statements)
            findings.append({"criterion_id": criterion.id, "status": "supported", "evidence": [
                {"source_id": found[0], "passage": found[1], "claim": found[2]}]} if found else
                {"criterion_id": criterion.id, "status": "unknown", "reason": missing})

        def cite(path: str, sentence: str, claim: str):
            return {"source_id": located[path].id, "passage": sentence, "claim": claim} if path in located else None
        facts = [{"kind": kind, "evidence": evidence} for kind, (path, sentence, claim) in company.facts.items()
                 if (evidence := cite(path, sentence, claim))]
        people = []
        if company.person and (evidence := cite(company.person[0], company.person[3],
                                                f"{company.person[1]} is {company.person[2]} at {company.name}.")):
            people.append({"name": company.person[1], "role": company.person[2], "evidence": evidence})
        return validate_extraction({
            "name": company.name, "findings": findings,
            "exclusion_findings": [{"exclusion_id": f"exclude-{index + 1}", "status": "unknown",
                                    "reason": "Sample data: the sample pages do not address this exclusion."}
                                   for index in range(len(profile.exclusions))],
            "company_facts": facts, "people": people,
            "hypotheses": [{"text": "Sample hypothesis: onboarding reviews might be relevant to this company",
                            "assumptions": ["No need or buying intent has been established"]}],
        }, profile, candidate.domain, sources)

    def verify(self, profile: Profile, record: Research) -> Verification:
        time.sleep(.3 * self.pace)
        return Verification(judgments=[Judgment(assessment_id=item["assessment_id"], verdict="entailed",
                                                reason="Sample data: the quoted sample passage states this.")
                                       for item in assessments(profile, record)])


def sample_providers(pace: float = 1.0):
    """Search, model and fetch for a sample run. Each step pauses briefly so the progress view can be followed."""
    return SampleSearch(pace), SampleModel(pace), sample_fetch(pace)
