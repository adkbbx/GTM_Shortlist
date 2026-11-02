"""Recruiters, staffing firms and agencies (2 November): a hiring search for SDRs finds recruiters posting for their
clients. Their hiring belongs to someone else, and when the seller sells to product companies they are not buyers.
Pages and companies here are SYNTHETIC, on reserved .example domains."""
from types import SimpleNamespace

from shortlist.agent.competitors import WORKS_FOR_OTHERS, disqualifier_rules
from shortlist.agent.investigation import Investigation
from shortlist.agent.models import CandidateRef, SellerProfile, Statement
from shortlist.agent.pages import page_from_document
from shortlist.relevance import CLIENT_ROLE, staffing_firm


def test_staffing_firms_are_told_apart_from_software_about_staffing():
    for text in ("Apex Talent | Recruitment agency for SaaS startups", "We are a staffing firm placing SDRs",
                 "Outsourced SDRs that book meetings", "Executive search for venture-backed companies",
                 "Lead generation agency"):
        assert staffing_firm(text), text
    for text in ("Scheduling and staffing software for restaurants", "Recruiting software for hiring teams",
                 "Hire the top 3% of freelance talent", "We help teams answer customer chats"):
        assert not staffing_firm(text), text


def test_a_role_written_for_a_client_is_recognised():
    assert CLIENT_ROLE.search("Our client, a Series A fintech, is hiring an SDR")
    assert CLIENT_ROLE.search("We are recruiting on behalf of a client in London")
    assert CLIENT_ROLE.search("Confidential search: Head of Sales")
    # A company's own posting talks about its clients in the plural; that is not a role written for a client.
    assert not CLIENT_ROLE.search("You will own relationships with our clients and their teams")
    assert not CLIENT_ROLE.search("Join our sales team to grow our customer base")


def profile(buyer: str) -> SellerProfile:
    return SellerProfile(website="https://seller.example/", domain="seller.example", buyer=Statement(value=buyer))


def test_the_rule_applies_only_when_the_seller_sells_to_product_companies():
    assert WORKS_FOR_OTHERS in [r.id for r in disqualifier_rules(profile("B2B SaaS startups that need pipeline"), [])]
    assert WORKS_FOR_OTHERS not in [r.id for r in disqualifier_rules(profile("Recruiting agencies and staffing firms"), [])]
    assert WORKS_FOR_OTHERS not in [r.id for r in disqualifier_rules(profile("Businesses of any size"), [])]


def test_a_recruiting_firm_is_rejected_from_its_own_homepage_before_paid_research():
    home = page_from_document("https://apex-talent.example/", (
        b"<html><head><title>Apex Talent</title></head><body><h1>Apex Talent</h1>"
        b"<p>We are a recruitment agency placing SDRs and AEs at SaaS startups.</p></body></html>"), None)
    rules = disqualifier_rules(profile("B2B SaaS startups that need pipeline"), [])
    events = []
    ctx = SimpleNamespace(rules=rules, emit=lambda *args, **kwargs: events.append(args[1]))
    investigation = Investigation(CandidateRef(domain="apex-talent.example", name="Apex Talent",
                                               url="https://apex-talent.example/"), ctx)
    investigation.home = home
    assert investigation.works_for_others()
    item = investigation.result.evidence[0]
    assert (item.claim_type, item.criterion_id, item.found_by) == ("disqualifier", WORKS_FOR_OTHERS, "scan")
    assert item.quote.text == "We are a recruitment agency placing SDRs and AEs at SaaS startups."
    assert "skipping deeper research" in events[0]

    ctx.rules = disqualifier_rules(profile("Recruiting agencies and staffing firms"), [])
    other = Investigation(CandidateRef(domain="apex-talent.example", name="Apex Talent",
                                       url="https://apex-talent.example/"), ctx)
    other.home = home
    assert not other.works_for_others()  # a seller to recruiters keeps them
