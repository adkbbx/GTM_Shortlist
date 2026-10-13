import pytest
from pydantic import ValidationError

from shortlist.domain import Criterion, Evidence, Observed, Profile, Unknown, qualify


@pytest.fixture
def profile():
    return Profile(seller_url="https://eygentic.com", offer="Acquisition research and experiments",
                   target="Private AI B2B SaaS startups", criteria=(Criterion(id="ai", description="AI software"),
                   Criterion(id="private", description="Privately held startup")))


def test_confirmation_is_immutable(profile):
    with pytest.raises(ValidationError):
        profile.target = "changed"


def test_missing_criterion_is_unknown(profile):
    assert qualify(profile, ()) == "needs_verification"


def test_contradiction_excludes_even_with_other_unknown(profile):
    evidence = Evidence(source_id="s", passage="We are a publicly listed business.", claim="Publicly listed")
    assert qualify(profile, (Observed(status="contradicted", criterion_id="private", evidence=(evidence,)),)) == "does_not_fit"


def test_supported_requires_evidence():
    with pytest.raises(ValidationError):
        Observed(status="supported", criterion_id="ai", evidence=())


def test_duplicate_criteria_rejected(profile):
    with pytest.raises(ValidationError):
        Profile(**{**profile.model_dump(), "criteria": [profile.criteria[0], profile.criteria[0]]})


def test_unknown_does_not_become_match(profile):
    assert qualify(profile, (Unknown(criterion_id="ai", reason="No source"),)) == "needs_verification"
