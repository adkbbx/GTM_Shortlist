"""Where a need shows (2 November): vanta.com's needs ("publishes a trust center", "lists SOC 2 work") appear on a
company's own site, but every own-site quote was refused as need, so nothing could be Shortlisted. A need signal now
says whether a company's own site can show it. Quotes here are SYNTHETIC."""
from datetime import UTC, date, datetime

from shortlist.agent.models import EvidenceItem, Quote, SkepticDecision
from shortlist.agent.skeptic import OWN_SITE_NEED, apply_rules
from shortlist.agent.verdict import fresh

TODAY = date(2026, 11, 2)


def item(criterion: str, published: date | None = None, source: str = "own_site") -> EvidenceItem:
    return EvidenceItem(claim_type="need", criterion_id=criterion, claim="Lists its SOC 2 work",
                        quote=Quote(text="Trailgear is SOC 2 Type I audited; Type II is in progress.",
                                    url="https://trailgear.example/security", source_type=source,
                                    published_date=published, fetched_at=datetime(2026, 11, 2, 9, tzinfo=UTC)))


def test_own_site_proves_only_the_needs_marked_for_it():
    supports = lambda e: SkepticDecision(evidence_id=e.id, decision="supports", decided_by="skeptic")
    trust = item("need-1")
    assert apply_rules(trust, supports(trust), {"need-1"}).decision == "supports"
    pitch = item("need-2")  # "needs more pipeline" on its own marketing is not evidence
    decided = apply_rules(pitch, supports(pitch), {"need-1"})
    assert (decided.decision, decided.reason, decided.decided_by) == ("insufficient", OWN_SITE_NEED, "rule")


def test_a_need_its_own_site_states_today_is_current_unless_the_page_is_dated_old():
    assert fresh(item("need-1"), TODAY, {"need-1"})
    assert not fresh(item("need-1"), TODAY)  # not a need its own site may show
    assert not fresh(item("need-1", published=date(2024, 3, 1)), TODAY, {"need-1"})
    assert fresh(item("need-1", published=date(2026, 10, 1)), TODAY, {"need-1"})
