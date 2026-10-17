"""Saved market observations and proposed campaigns before target confirmation."""
import re
from typing import Annotated, Literal

from pydantic import Field, StringConstraints, model_validator

from shortlist.domain import Candidate, Criterion, Value
from shortlist.fetch import canonical_url, domain_of
from shortlist.relevance import candidate_issue, company_page_issue, seller_marketing_criterion
from shortlist.selection import discussion_page

Trimmed = Annotated[str, StringConstraints(strip_whitespace=True)]
PRIVATE_CONDITION = re.compile(
    r"(?:poor|low|declining|stagnating|bad) (?:\w+ ){0,2}lead quality|pipeline volatility|poor .*conversion|low .*conversion|"
    r"lack of (?:historical )?data|without .*(?:strategy|icp)|needs? help|struggl|willing to buy|budget for|"
    r"^(?:needs?|seeks?|requires?)\b|complex (?:sales )?pipeline|high-volume personalized outreach",
    re.IGNORECASE,
)


class Campaign(Value):
    name: Trimmed = Field(min_length=3, max_length=100)
    target: Trimmed = Field(min_length=5, max_length=1000)
    rationale: Trimmed = Field(min_length=10, max_length=1000)
    criteria: tuple[Criterion, ...] = Field(min_length=1, max_length=6)
    search_terms: Trimmed = Field(default="", max_length=300)
    hypotheses: tuple[Annotated[str, StringConstraints(strip_whitespace=True, min_length=3, max_length=500)], ...] = Field(default=(), max_length=6)
    signals_to_check: tuple[Annotated[str, StringConstraints(strip_whitespace=True, min_length=3, max_length=200)], ...] = Field(default=(), max_length=4)

    @model_validator(mode="after")
    def unique_criteria(self):
        if len({c.id for c in self.criteria}) != len(self.criteria):
            raise ValueError("Campaign criteria require unique identifiers")
        return self


class CampaignPlan(Value):
    campaigns: tuple[Campaign, ...] = Field(max_length=6)
    issues: tuple[Trimmed, ...] = Field(default=(), max_length=4)

    @model_validator(mode="after")
    def distinct_names(self):
        if len({c.name.casefold() for c in self.campaigns}) != len(self.campaigns):
            raise ValueError("Campaign names must be distinct")
        return self


class MarketResearch(Value):
    competitors: tuple[Candidate, ...] = Field(default=(), max_length=15)
    campaigns: tuple[Campaign, ...] = Field(default=(), max_length=6)
    status: Literal["saved", "partial"]
    issues: tuple[str, ...] = Field(default=(), max_length=8)


def read_campaign_plan(data, *, distinct_targets: bool = False) -> CampaignPlan:
    plan = data if isinstance(data, CampaignPlan) else CampaignPlan.model_validate(data)
    campaigns = []
    adjusted = False
    seller_claims = False
    seen_targets = set()
    repeated = False
    for campaign in plan.campaigns:
        private = [c.description for c in campaign.criteria if PRIVATE_CONDITION.search(c.description)]
        seller_claims = seller_claims or any(seller_marketing_criterion(c.description) for c in campaign.criteria)
        criteria = tuple(c for c in campaign.criteria if not PRIVATE_CONDITION.search(c.description)
                         and not seller_marketing_criterion(c.description))
        if not criteria:
            adjusted = adjusted or bool(private)
            continue
        target_key = " ".join(re.findall(r"[a-z0-9]+", campaign.target.casefold()))
        if distinct_targets and target_key in seen_targets:
            repeated = True
            continue
        seen_targets.add(target_key)
        search_terms = campaign.search_terms
        if PRIVATE_CONDITION.search(search_terms):
            search_terms = ""
            adjusted = True
        adjusted = adjusted or bool(private)
        hypotheses = tuple(dict.fromkeys((*campaign.hypotheses, *private)))[:6]
        campaigns.append(campaign.model_copy(update={"criteria": criteria, "search_terms": search_terms,
                                                     "hypotheses": hypotheses}))
    issues = list(plan.issues)
    message = "Conditions involving private performance were kept as hypotheses; campaigns without public criteria were omitted."
    if adjusted and message not in issues:
        issues.append(message)
    seller_message = "Seller marketing claims were omitted from customer criteria; review the proposed buyer segment."
    if seller_claims and seller_message not in issues:
        issues.append(seller_message)
    if repeated:
        issues.append("Repeated customer segments were omitted; product use cases alone do not establish distinct audiences.")
    return CampaignPlan(campaigns=tuple(campaigns), issues=tuple(dict.fromkeys(issues))[:4])


def market_candidates(values, seller_url, *, offer: str = "", strict: bool = False):
    seller = domain_of(seller_url)
    unique = {}
    for value in values:
        candidate = value if isinstance(value, Candidate) else Candidate.model_validate(value)
        if canonical_url(candidate.url) != candidate.url or domain_of(candidate.url) != candidate.domain:
            raise ValueError("Competitor search returned a mismatched website identity")
        if strict and (company_page_issue(candidate.url, candidate.name, strict=True) or
                       not offer_overlap(offer, candidate.name + " " + candidate.excerpt)):
            continue
        if candidate.domain != seller and not discussion_page(candidate.url) and not candidate_issue(candidate):
            unique.setdefault(candidate.domain, candidate)
    return list(unique.values())[:15]


OFFER_FILLER = frozenset(["a", "an", "the", "and", "or", "to", "of", "for", "in", "on", "by", "with", "from", "as", "is", "are", "it", "its", "this", "that", "their", "our", "your", "we", "they", "any", "all", "builds", "building", "provides", "providing", "acts", "layer", "various", "sources", "using", "use", "helps", "help", "get", "run", "launch", "focused", "grow", "plays", "systems", "functions", "companies", "company", "businesses", "business", "software", "platform", "infrastructure", "integrates", "integrating", "offering", "offers", "through", "within", "can", "will", "similar", "official", "websites"])


def offer_terms(offer: str) -> list[str]:
    # Preserve complete category terms rather than cutting a marketing sentence mid-thought.
    return list(dict.fromkeys(word for word in re.findall(r"[a-z][a-z0-9-]+", offer.casefold())
                              if len(word) > 2 and word not in OFFER_FILLER))


def offer_overlap(offer: str, observation: str) -> bool:
    terms = offer_terms(offer)
    if not terms:
        return True
    observed = set(re.findall(r"[a-z][a-z0-9-]+", observation.casefold()))
    return len(observed.intersection(terms)) >= min(2, len(terms))


def competitor_query(offer: str, seller_url: str, *, policy: int = 2) -> str:
    if policy < 2:
        description = " ".join(offer.split()[:24])
    else:
        seller = domain_of(seller_url).split(".")[0]
        description = " ".join(term for term in offer_terms(offer) if term != seller).split()
        description = " ".join(description[:10]) or "business services"
    return f'{description} similar companies official websites -site:{domain_of(seller_url)}'


def reviewed_market(raw, seller_url: str, offer: str) -> MarketResearch | None:
    """Read-only projection for historical evidence; never rewrite paid outcomes."""
    if raw is None:
        return None
    saved = raw if isinstance(raw, MarketResearch) else MarketResearch.model_validate(raw)
    candidates = market_candidates(saved.competitors, seller_url, offer=offer, strict=True)
    plan = read_campaign_plan(CampaignPlan(campaigns=saved.campaigns), distinct_targets=True)
    issues = list(saved.issues) + list(plan.issues)
    removed = len(saved.competitors) - len(candidates)
    if removed:
        issues.append(f"{removed} saved search observations excluded: page purpose or offer relevance was not established.")
    issues = tuple(dict.fromkeys(issues))[:8]
    return MarketResearch(competitors=tuple(candidates), campaigns=plan.campaigns,
                          status="partial" if issues else saved.status, issues=issues)
