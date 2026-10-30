"""Optional user corrections, merged on top of what the agent inferred. None of them is ever required."""
from dataclasses import dataclass, field

from shortlist.agent.competitors import clean_domain, disqualifier_rules
from shortlist.agent.models import Competitor, FitCriterion, Interpretation, Overrides, RunResult, Statement


@dataclass
class Changes:
    added_competitors: list[Competitor] = field(default_factory=list)
    removed_competitors: list[str] = field(default_factory=list)
    edited_criteria: set[str] = field(default_factory=set)
    added_criteria: set[str] = field(default_factory=set)
    count_changed: bool = False
    target_size_changed: bool = False

    @property
    def needs_research(self) -> bool:
        return bool(self.added_criteria)


def merge(old: Overrides, new: Overrides) -> Overrides:
    def unique(*lists):
        seen, values = set(), []
        for value in (v.strip() for values_ in lists for v in values_):
            if value and value.casefold() not in seen:
                seen.add(value.casefold())
                values.append(value)
        return values

    added = unique(old.add_competitors, new.add_competitors)
    removed = unique(old.remove_competitors, new.remove_competitors)
    # The latest choice for a domain wins: adding again undoes a removal and the other way round.
    added = [d for d in added if d.casefold() not in {r.casefold() for r in new.remove_competitors}]
    removed = [d for d in removed if d.casefold() not in {a.casefold() for a in new.add_competitors}]
    criteria = {c.id: c for c in old.criteria}
    for change in new.criteria:
        previous = criteria.get(change.id)
        criteria[change.id] = change if previous is None else previous.model_copy(
            update={key: value for key, value in change.model_dump().items() if value is not None})
    return Overrides(add_competitors=added[:10], remove_competitors=removed[:20],
                     exclusions=unique(old.exclusions, new.exclusions)[:20], criteria=list(criteria.values())[:12],
                     company_count=new.company_count or old.company_count,
                     interpretation=new.interpretation or old.interpretation,
                     offer=new.offer or old.offer, buyer=new.buyer or old.buyer,
                     target_size=new.target_size or old.target_size)


def apply_competitors(result: RunResult, overrides: Overrides, changes: Changes):
    removed = {d for d in (clean_domain(v) for v in overrides.remove_competitors) if d}
    kept = []
    for competitor in result.competitors:
        if competitor.domain in removed:
            changes.removed_competitors.append(competitor.domain)
        else:
            kept.append(competitor)
    by_domain = {c.domain: c for c in kept}
    for value in overrides.add_competitors:
        domain = clean_domain(value)
        if domain is None or domain in removed:
            continue
        existing = by_domain.get(domain)
        if existing is not None and existing.classification == "direct":
            continue
        name = existing.name if existing else domain.split(".")[0].replace("-", " ").title()
        marked = Competitor(name=name, domain=domain, classification="direct", origin="user",
                            same_job=existing.same_job if existing else None,
                            same_buyer=existing.same_buyer if existing else None,
                            reason="Marked as a direct competitor by you", found_via="you")
        by_domain[domain] = marked
        changes.added_competitors.append(marked)
    result.competitors = list(by_domain.values())


def apply_criteria(result: RunResult, overrides: Overrides, changes: Changes):
    profile = result.profile
    if profile is None:
        return
    criteria = {c.id: c for c in profile.fit_criteria}
    for change in overrides.criteria:
        current = criteria.get(change.id)
        if current is None:
            if change.text and change.enabled is not False:
                criteria[change.id] = FitCriterion(id=change.id, text=change.text, origin="user",
                                                   required=True if change.required is None else change.required)
                changes.added_criteria.add(change.id)
            continue
        update = {}
        if change.text and change.text != current.text:
            update["text"] = change.text
            changes.edited_criteria.add(change.id)
        if change.required is not None and change.required != current.required:
            update["required"] = change.required
        if change.enabled is not None and change.enabled != current.enabled:
            update["enabled"] = change.enabled
        if update:
            criteria[change.id] = current.model_copy(update=update)
    profile.fit_criteria = list(criteria.values())


def apply_reading(result: RunResult, overrides: Overrides, reading: Interpretation | None = None):
    """A chosen interpretation or typed offer/buyer replaces the inferred one. Typed text is input, not a claim."""
    profile = result.profile
    if profile is None:
        return
    if reading is not None:
        profile.offer = Statement(value=reading.offer, quotes=reading.quotes, origin="interpretation")
        profile.buyer = Statement(value=reading.buyer, quotes=reading.quotes, origin="interpretation")
        profile.interpretations = [reading]
    if overrides.offer:
        profile.offer = Statement(value=overrides.offer, origin="user")
    if overrides.buyer:
        profile.buyer = Statement(value=overrides.buyer, origin="user")


def apply_target_size(result: RunResult, overrides: Overrides, changes: Changes):
    """The size you set replaces the inferred one; saved evidence for the size rule is judged again against it."""
    profile = result.profile
    if profile is None or not overrides.target_size:
        return
    if profile.target_size is None or profile.target_size.value != overrides.target_size:
        profile.target_size = Statement(value=overrides.target_size, origin="user")
        changes.target_size_changed = True


def apply(result: RunResult, overrides: Overrides) -> Changes:
    changes = Changes()
    apply_competitors(result, overrides, changes)
    apply_criteria(result, overrides, changes)
    apply_target_size(result, overrides, changes)
    result.disqualifiers = disqualifier_rules(result.profile, result.competitors)
    if overrides.company_count and overrides.company_count != result.company_count:
        result.company_count = overrides.company_count
        changes.count_changed = True
    result.overrides = overrides
    return changes
