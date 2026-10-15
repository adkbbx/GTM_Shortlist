import hashlib
from datetime import UTC, date, datetime

import pytest

from shortlist.domain import Source
from shortlist.signals import company_signals, explicit_date

AS_OF = date(2026, 10, 15)


def source(text, domain="company.example"):
    return Source(url=f"https://{domain}/news", company_domain=domain, title="Labelled fixture", text=text,
                  content_hash=hashlib.sha256(text.encode()).hexdigest(), retrieved_at=datetime(2026, 10, 15, tzinfo=UTC))


@pytest.mark.parametrize("text,label", [
    ("On 2026-10-01, we are hiring a sales manager.", "Hiring"),
    ("On October 1, 2026, we raised $5 million in funding.", "Funding"),
    ("On 1 October 2026, we opened our new Berlin office.", "Expansion"),
    ("On October 1 2026, we launched our logistics platform.", "Product launch"),
])
def test_explicit_dated_first_party_statements_retain_exact_provenance(text, label):
    page = source(text)
    signals = company_signals("company.example", (page,), AS_OF)
    assert len(signals) == 1
    signal = signals[0]
    assert signal.label == label and signal.event_date == date(2026, 10, 1)
    assert signal.passage == page.text and signal.source_id == page.id and signal.source_url == page.url
    assert signal.observed_at == page.retrieved_at


@pytest.mark.parametrize("text", [
    "We are hiring a sales manager.",
    "Copyright 2026-10-01. We are hiring a sales manager.",
    "On 2026-11-01, we are hiring a sales manager.",
    "On 2025-10-01, we are hiring a sales manager.",
    "On 2026-10-01, we are not hiring a sales manager.",
    'On 2026-10-01, our client said "we are hiring a sales manager".',
    "On 2026-10-01, the quote is 'we are hiring a sales manager'.",
    "On 2026-10-01, our partner says we raised $5 million.",
    "On 2026-10-01 compared with 2026-09-01, we are hiring a sales manager.",
    "On 2026-10-40, we are hiring a sales manager.",
    "On 2026-10-01, they are hiring a sales manager.",
    "On 2026-10-01, we raised concerns about data privacy.",
    "On 2026-10-01, we opened the file attached to an email.",
])
def test_ambiguous_undated_third_party_or_non_event_text_receives_no_signal_priority(text):
    page = source(text).model_copy(update={"published_at": datetime(2026, 10, 1, tzinfo=UTC)})
    assert company_signals("company.example", (page,), AS_OF) == ()


def test_company_identity_and_campaign_relevance_are_independent_of_presence():
    page = source("On 2026-10-01, we raised $5 million.")
    assert company_signals("other.example", (page,), AS_OF) == ()
    assert not company_signals("company.example", (page,), AS_OF, ("Hiring a sales team",))[0].campaign_relevant
    assert company_signals("company.example", (page,), AS_OF, ("Funding announcements",))[0].campaign_relevant
    assert explicit_date("2026-10-40") is None
