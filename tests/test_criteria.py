"""Rarely-public fit checks: the same table scripts/check_fit_checks.mjs runs against web/criteria.ts."""
import pytest

from shortlist.criteria import rarely_public
from shortlist.providers import recover_customer_draft

FLAGGED = [
    "Privately held startup, with explicit current evidence of ownership and startup stage", "Seed or Series A funding stage",
    "Unsure if they are targeting the right customer profile (ICP).", "Uncertain if the current messaging resonates with the target audience.",
    "Spending on growth/channels without knowing which specific one produces conversations.",
    "Uncertainty regarding whether the current offer converts.", "Want to scale growth but lack confidence that the system/infrastructure is ready.",
    "Venture-backed SaaS company", "Annual revenue of more than $10M", "Has a budget for outbound tools", "Planning to expand into Europe",
    "Recently raised a Series B",
]
OBSERVABLE = [
    "Offers software with artificial intelligence as a core capability", "Sells software to businesses",
    "Offers software as a subscription or hosted service", "SaaS company", "B2B company", "Sells revenue operations software",
    "Offers investor relations software", "Provides property valuation services", "Confidential computing platform",
    "Sells spend management software", "Has an implementation team that runs customer onboarding",
    "Lists a partner program on its website", "Publishes pricing for business plans", "Has 50 or more employees",
    "Offers budgeting software for finance teams",
]


@pytest.mark.parametrize("text,expected", [(text, True) for text in FLAGGED] + [(text, False) for text in OBSERVABLE])
def test_rarely_public_checks_are_told_apart_from_observable_ones(text, expected):
    assert rarely_public(text) is expected


def test_drafted_ownership_and_funding_checks_start_as_nice_to_have():
    draft = recover_customer_draft({
        "seller_offer": "Customer acquisition experiments for software companies", "target_customer": "B2B SaaS startups",
        "customer_criteria": [
            {"id": "software", "subject": "target_customer", "customer_characteristic": "Sells software to businesses", "required": True},
            {"id": "stage", "subject": "target_customer", "customer_characteristic": "Seed or Series A funding stage", "required": True},
            {"id": "private", "subject": "target_customer", "customer_characteristic": "Privately held startup", "required": True},
        ], "unknowns": []})
    assert {c.id: c.required for c in draft.criteria} == {"software": True, "stage": False, "private": False}
    assert not draft.criteria_issues  # Kept for the shortlist order and the conversation, not removed.


def test_a_draft_keeps_a_required_check_when_every_check_is_rarely_public():
    draft = recover_customer_draft({
        "seller_offer": "Customer acquisition experiments for software companies", "target_customer": "Funded startups",
        "customer_criteria": [
            {"id": "stage", "subject": "target_customer", "customer_characteristic": "Seed or Series A funding stage", "required": True},
            {"id": "private", "subject": "target_customer", "customer_characteristic": "Privately held startup", "required": False},
        ], "unknowns": []})
    assert {c.id: c.required for c in draft.criteria} == {"stage": True, "private": False}


def test_fit_needs_at_least_one_required_check():
    from shortlist.domain import Criterion, Observed, Profile, qualify
    profile = Profile(seller_url="https://seller.example/", offer="Customer acquisition research", target="Business software",
                      criteria=(Criterion(id="team", description="Lists a customer success team", required=False),))
    supported = Observed(status="supported", criterion_id="team", evidence=(
        {"source_id": "s", "passage": "Our customer success team helps.", "claim": "Labelled claim"},))
    # A supported nice-to-have check alone never makes a company a fit.
    assert qualify(profile, (supported,)) == "needs_verification"
