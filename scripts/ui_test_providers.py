"""Explicitly labelled synthetic providers shared by browser verification servers."""

import hashlib
import time
from datetime import UTC, datetime, timedelta

from shortlist.domain import Candidate, Criterion, Source
from shortlist.fetch import domain_of
from shortlist.providers import ProviderError, SellerDraft, validate_extraction
from shortlist.verification import Judgment, Verification, assessments


class FixtureSearch:
    name = "labelled_test_fixture"

    def search(self, query, seller_url):
        if seller_url is None and query.startswith('"No matches fixture"'):
            return []
        if seller_url is None and query.startswith('"Lookup unavailable fixture"'):
            raise ProviderError("Labelled unavailable website lookup")
        company = query.split('"')[1] if seller_url is None else "Example"
        return [
            Candidate(
                domain=f"example-{index}.com",
                name=f"{company} {index} (test fixture)",
                url=f"https://example-{index}.com/",
                query=query,
                provider=self.name,
                excerpt="TEST FIXTURE. Customer acquisition experiments and growth services for AI business software startups.",
            )
            for index in (range(1, 17) if 'similar companies official websites' in query
                          else (1, 2, 3) if 'Three comparison companies' in query else (1, 2))
        ]


def fixture_fetch(url, expected_domain=None):
    time.sleep(0.15)  # Observable test-provider work, not a simulated UI progress timer.
    text = (
        "TEST FIXTURE. This is synthetic test content, not a real company. "
        "We provide artificial intelligence software for business operations as a hosted subscription. "
        "Example Labs is a privately held startup. No buying intent has been observed."
    )
    yesterday = (datetime.now(UTC) - timedelta(days=1)).date().isoformat()
    if expected_domain != "activity-fixture.example" or url.endswith("/news"):
        text += f" On {yesterday}, we are hiring a sales manager."
    if expected_domain == "example-1.com":
        text += " Example Labs is headquartered in Canada. Our team has 24 employees. Alex Morgan is our CEO."
    company_domain = expected_domain or domain_of(url)
    links = (
        (f"https://{company_domain}/about", f"https://{company_domain}/pricing")
        if url.endswith("/")
        else ()
    )
    return Source(
        url=url,
        company_domain=company_domain,
        title="Labelled test source",
        text=text,
        content_hash=hashlib.sha256(text.encode()).hexdigest(),
        research_links=links,
        activity_links=(f"https://{company_domain}/news",) if expected_domain == "activity-fixture.example" and url.endswith("/") else (),
    )


class FixtureModel:
    name = "labelled_test_fixture"

    def seller(self, source):
        return SellerDraft(
            offer="Test fixture: customer acquisition experiments for software businesses",
            target="Private AI B2B SaaS startups",
            criteria=[
                Criterion(id="ai", description="Offers AI software to businesses"),
                Criterion(id="private", description="Privately held startup"),
            ],
            unknowns=[],
        )

    def market(self, draft, candidates):
        from shortlist.market import Campaign, CampaignPlan
        return CampaignPlan(campaigns=tuple(Campaign(name=f"Labelled campaign {i}",
            target=f"Private AI B2B SaaS startups in test segment {i}",
            rationale="TEST FIXTURE campaign hypothesis, not an observed market fact.",
            criteria=tuple(draft.criteria), search_terms=f"AI business software test segment {i}",
            signals_to_check=("Hiring a sales team",)) for i in range(1, 7)))

    def verify(self, profile, record):
        time.sleep(0.2)
        return Verification(
            judgments=[
                Judgment(
                    assessment_id=a["assessment_id"],
                    verdict="entailed",
                    reason="Labelled synthetic fixture judgment",
                )
                for a in assessments(profile, record)
            ]
        )

    def research(self, profile, candidate, sources):
        time.sleep(0.5)
        findings = []
        for criterion in profile.criteria:
            if candidate.domain == "example-2.com" and criterion.id == "private":
                findings.append(
                    {
                        "criterion_id": criterion.id,
                        "status": "unknown",
                        "reason": "Test fixture: ownership needs an independent dated source",
                    }
                )
            else:
                passage = (
                    "Example Labs is a privately held startup."
                    if criterion.id == "private"
                    else "We provide artificial intelligence software for business operations as a hosted subscription."
                )
                findings.append(
                    {
                        "criterion_id": criterion.id,
                        "status": "supported",
                        "evidence": [
                            {
                                "source_id": sources[1].id if criterion.id == "private" else sources[0].id,
                                "passage": passage,
                                "claim": "Test fixture observation from supplied text",
                            }
                        ],
                    }
                )
        exclusion_findings = []
        for index, _ in enumerate(profile.exclusions):
            if candidate.domain == "example-1.com":
                passage = (
                    "Example Labs is headquartered in Canada."
                    if index == 0
                    else "Example Labs is a privately held startup."
                )
                exclusion_findings.append(
                    {
                        "exclusion_id": f"exclude-{index + 1}",
                        "status": "matched" if index == 0 else "cleared",
                        "evidence": [
                            {
                                "source_id": sources[0].id,
                                "passage": passage,
                                "claim": "Test fixture exclusion assessment",
                            }
                        ],
                    }
                )
            else:
                exclusion_findings.append(
                    {
                        "exclusion_id": f"exclude-{index + 1}",
                        "status": "unknown",
                        "reason": "Test fixture: no independent current evidence to assess this exclusion",
                    }
                )
        return validate_extraction(
            {
                "name": f"Example research company {candidate.domain} (test fixture)",
                "findings": findings,
                "people": [{"name": "Alex Morgan", "role": "CEO", "evidence": {
                    "source_id": sources[0].id, "passage": "Alex Morgan is our CEO.",
                    "claim": "Alex Morgan is CEO at this synthetic company."}}]
                    if candidate.domain == "example-1.com" else [],
                "company_facts": [
                    {"kind": kind, "evidence": {"source_id": sources[0].id, "passage": passage, "claim": claim}}
                    for kind, passage, claim in [
                        ("description", "We provide artificial intelligence software for business operations as a hosted subscription.",
                         "AI software for business operations, sold as a hosted subscription."),
                        *([("location", "Example Labs is headquartered in Canada.", "Headquartered in Canada."),
                           ("team_size", "Our team has 24 employees.", "24 employees, as stated on the saved page.")]
                          if candidate.domain == "example-1.com" else []),
                    ]
                ],
                "exclusion_findings": exclusion_findings,
                "hypotheses": [
                    {
                        "text": "Test fixture: acquisition experiments might be relevant",
                        "assumptions": ["No need or buying intent has been established"],
                    }
                ],
            },
            profile,
            candidate.domain,
            sources,
        )
