"""Saved market observations and proposed campaigns before target confirmation."""
import re
from typing import Annotated, Literal

from pydantic import Field, StringConstraints, model_validator

from shortlist.domain import Candidate, Criterion, Value
from shortlist.fetch import canonical_url, domain_of
from shortlist.selection import discussion_page

Trimmed = Annotated[str, StringConstraints(strip_whitespace=True)]
PRIVATE_CONDITION = re.compile(
    r"(?:poor|low|declining|stagnating|bad) (?:\w+ ){0,2}lead quality|pipeline volatility|poor .*conversion|low .*conversion|"
    r"lack of (?:historical )?data|without .*(?:strategy|icp)|needs? help|struggl|willing to buy|budget for",
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


def read_campaign_plan(data) -> CampaignPlan:
    plan = data if isinstance(data, CampaignPlan) else CampaignPlan.model_validate(data)
    campaigns = []
    adjusted = False
    for campaign in plan.campaigns:
        private = [c.description for c in campaign.criteria if PRIVATE_CONDITION.search(c.description)]
        criteria = tuple(c for c in campaign.criteria if not PRIVATE_CONDITION.search(c.description))
        if not criteria:
            adjusted = True
            continue
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
    return CampaignPlan(campaigns=tuple(campaigns), issues=tuple(issues[:4]))


def market_candidates(values, seller_url):
    seller = domain_of(seller_url)
    unique = {}
    for value in values:
        candidate = value if isinstance(value, Candidate) else Candidate.model_validate(value)
        if canonical_url(candidate.url) != candidate.url or domain_of(candidate.url) != candidate.domain:
            raise ValueError("Competitor search returned a mismatched website identity")
        if candidate.domain != seller and not discussion_page(candidate.url):
            unique.setdefault(candidate.domain, candidate)
    return list(unique.values())[:15]


def competitor_query(offer: str, seller_url: str) -> str:
    description = " ".join(offer.split()[:24])
    return f'{description} similar companies official websites -site:{domain_of(seller_url)}'
