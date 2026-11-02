"""Stage E: the verdict is deterministic code over skeptic decisions. The models never decide it."""
from datetime import date, timedelta

from shortlist.agent.models import (
    BUDGET_REACHED,
    CompanyResult,
    DisqualifierRule,
    EvidenceItem,
    SellerProfile,
    Verdict,
)

FRESH_DAYS = 180
RULE_ORDER = {"uses_direct_competitor": 0, "is_competitor": 1, "is_existing_customer": 2,
              "outside_stated_size_or_region": 3, "inactive": 4, "works_for_others": 5}


def excluded_by(company: CompanyResult, exclusions: list[str]) -> str | None:
    for entry in exclusions:
        value = entry.strip().casefold()
        if not value:
            continue
        if "." in value and " " not in value:
            domain = value.removeprefix("https://").removeprefix("http://").removeprefix("www.").split("/")[0]
            if company.domain == domain or company.domain.endswith("." + domain):
                return entry
        elif value in company.name.casefold() or value == company.domain.split(".")[0]:
            return entry
    return None


def fresh(item: EvidenceItem, today: date, own_site_ok: set[str] = frozenset()) -> bool:
    """Current: published within FRESH_DAYS, or a job posting found open on an applicant-tracking system during this
    run (a role still being hired for is current whenever it was first posted), or a need the company's own site may
    show (own_site_ok), read from that site during this run: the site states it today, unless the page is dated old."""
    read_today = abs((item.quote.fetched_at.date() - today).days) <= 1
    published = item.quote.published_date
    recent = published is not None and today - timedelta(days=FRESH_DAYS) <= published <= today + timedelta(days=1)
    if item.quote.open_posting and read_today:
        return True
    if item.claim_type == "need" and item.quote.source_type == "own_site" and item.criterion_id in own_site_ok \
            and read_today and (published is None or recent):
        return True
    return recent


def decide(company: CompanyResult, profile: SellerProfile, rules: list[DisqualifierRule], today: date,
           exclusions: list[str] = ()) -> Verdict:
    if entry := excluded_by(company, list(exclusions)):
        return Verdict(kind="rejected", summary=f"Excluded by you ({entry})")
    decisions = {d.evidence_id: d for d in company.decisions}
    supported = [e for e in company.evidence if (d := decisions.get(e.id)) is not None and d.decision == "supports"]
    enabled = {rule.id: rule for rule in rules if rule.enabled}
    disqualifiers = sorted((e for e in supported if e.claim_type == "disqualifier" and e.criterion_id in enabled),
                           key=lambda e: (RULE_ORDER[enabled[e.criterion_id].rule], e.found_by != "scan",
                                          e.quote.location == "html"))
    if disqualifiers:
        item = disqualifiers[0]
        rule = enabled[item.criterion_id]
        return Verdict(kind="rejected", summary=rule.text, disqualifier=item, rule=rule.rule)

    gaps: list[str] = []
    if company.status == "budget_reached":
        gaps.append(BUDGET_REACHED)
    if company.error:
        gaps.append(f"Research incomplete: {company.error}")
    contradicted = {e.criterion_id for e in company.evidence
                    if e.claim_type == "fit" and (d := decisions.get(e.id)) is not None and d.decision == "contradicts"}
    for criterion in (c for c in profile.fit_criteria if c.enabled and c.required):
        if not any(e.claim_type == "fit" and e.criterion_id == criterion.id for e in supported):
            prefix = "Not a fit" if criterion.id in contradicted else "Fit not confirmed"
            gaps.append(f"{prefix}: {criterion.text}")
    signals = [e for e in supported if e.claim_type in ("need", "timing")]
    own_ok = {signal.id for signal in profile.need_signals if signal.own_site}
    if not any(fresh(e, today, own_ok) for e in signals):
        if signals:
            gaps.append("Signs of need found, but none recent (from the last 6 months or an open job post)")
        else:
            gaps.append("No recent sign they need this (nothing from the last 6 months, no open job post)")
    if not company.checked_places:
        gaps.append("Competitor check didn't run")
    elif not company.disqualifier_check_completed:
        gaps.append("Competitor check incomplete")
    if not gaps:
        judged = {e.criterion_id for e in company.evidence
                  if (d := decisions.get(e.id)) is not None and d.decision in ("supports", "contradicts")}
        unconfirmed = [f"Not shown by a quote either way: {rule.text}" for rule in enabled.values()
                       if rule.rule == "outside_stated_size_or_region" and rule.id not in judged]
        return Verdict(kind="shortlisted",
                       summary="Strong fit, a recent sign they need this, and no competitor in use",
                       unconfirmed=unconfirmed)
    notes = [f"Could not read {page}" for page in company.blocked[:5]]
    return Verdict(kind="needs_look", summary="Needs a look", missing=gaps + notes)
