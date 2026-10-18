import hashlib

import pytest

from shortlist.domain import Candidate, Criterion, Profile, Source
from shortlist.providers import candidates_from_results, validate_extraction


@pytest.fixture
def example():
    profile = Profile(seller_url="https://eygentic.com", offer="Customer acquisition experiments",
                      target="Private AI software startups", criteria=(Criterion(id="ai", description="AI software"),))
    text = "We provide artificial intelligence software for business operations."
    source = Source(id="source-1", url="https://example.com", company_domain="example.com",
                    title="Example", text=text, content_hash=hashlib.sha256(text.encode()).hexdigest())
    return profile, source


def test_directory_duplicate_and_seller_filter():
    results = [{"url": "https://linkedin.com/company/example", "title": "Directory"},
               {"url": "https://example.com/", "title": "Example"},
               {"url": "https://www.example.com/pricing", "title": "Duplicate"},
               {"url": "https://eygentic.com", "title": "Seller"},
               {"url": "https://127.1", "title": "Unsafe"}]
    candidates = candidates_from_results(results, "AI startup", "fixture", "https://eygentic.com")
    assert len(candidates) == 1
    assert candidates[0].domain == "example.com"
    assert candidates[0].query == "AI startup"


@pytest.mark.parametrize("case", range(30))
def test_unavailable_or_fabricated_citations_become_unknown(example, case):
    profile, source = example
    raw = {"name": "Example", "findings": [{"status": "supported", "criterion_id": "ai", "evidence": [{
        "source_id": "wrong-company" if case % 2 else source.id,
        "passage": f"This invented source passage was never provided, case {case}", "claim": "Uses AI"}]}]}
    record = validate_extraction(raw, profile, "example.com", (source,))
    assert record.qualification == "needs_verification"
    assert record.findings[0].status == "unknown"


def test_real_passage_retained(example):
    profile, source = example
    raw = {"name": "Example", "findings": [{"status": "supported", "criterion_id": "ai", "evidence": [{
        "source_id": source.id, "passage": source.text, "claim": "AI business software"}]}]}
    record = validate_extraction(raw, profile, "example.com", (source,))
    assert record.qualification == "fits"
    assert record.sources[0].retrieved_at == source.retrieved_at


@pytest.mark.parametrize("passage,kept", [
    # Labelled text shaped like nice.com's homepage (18 October): zero-width spaces and a typographic apostrophe.
    ("The AI platform built for better customer experience. The world's leading brands trust Acme.", True),
    ("The AI platform built for \u200bbetter customer experience\u200b. The world’s leading brands trust Acme.", True),
    ("The AI platform built for the best customer experience. The world's leading brands trust Acme.", False),
    ("The AI platform built for better customer experience. The world's leading brands trust Acme!", False),
    ("the ai platform built for better customer experience. The world's leading brands trust Acme.", False),
])
def test_quote_ignores_only_invisible_characters_and_quote_marks(passage, kept):
    profile = Profile(seller_url="https://eygentic.com", offer="Customer acquisition experiments",
                      target="Private AI software startups", criteria=(Criterion(id="ai", description="AI software"),))
    text = "The AI platform built for \u200b\nbetter customer experience\u200b.\nThe world’s leading brands trust Acme."
    source = Source(id="source-1", url="https://acme.example", company_domain="acme.example", title="Acme", text=text,
                    content_hash=hashlib.sha256(text.encode()).hexdigest())
    raw = {"name": "Acme", "findings": [{"status": "supported", "criterion_id": "ai", "evidence": [{
        "source_id": source.id, "passage": passage, "claim": "AI software"}]}]}
    record = validate_extraction(raw, profile, "acme.example", (source,))
    assert (record.qualification == "fits") is kept and (record.findings[0].status == "unknown") is not kept


@pytest.mark.parametrize("claim,kept", [
    ("The presence of 'Channel Partnerships' in the navigation suggests the company is involved in partnerships.", False),
    ("The company may run a partner program.", False),
    ("The company likely sells AI software.", False),
    ("The company sells artificial intelligence software for business operations.", True),
    ("Founded in May 2020, the company sells AI software.", True),  # The month is not a hedge.
])
def test_a_claim_the_model_hedges_does_not_establish_a_check(example, claim, kept):
    profile, source = example
    raw = {"name": "Example", "findings": [{"status": "supported", "criterion_id": "ai", "evidence": [{
        "source_id": source.id, "passage": source.text, "claim": claim}]}]}
    finding = validate_extraction(raw, profile, "example.com", (source,)).findings[0]
    assert (finding.status == "supported") is kept
    if not kept:
        assert "inference" in finding.reason


def test_a_check_worded_as_a_hedge_can_be_restated_and_typographic_dashes_match(example):
    _, source = example
    # The live channel-partner check reads "indicators suggesting a need"; restating it is not the model hedging.
    profile = Profile(seller_url="https://eygentic.com", offer="Customer acquisition experiments", target="AI startups",
                      criteria=(Criterion(id="ai", description="Indicators suggesting a need for AI software"),))
    raw = {"name": "Example", "findings": [{"status": "supported", "criterion_id": "ai", "evidence": [{
        "source_id": source.id, "passage": source.text, "claim": "It sells AI software, suggesting a need for it."}]}]}
    assert validate_extraction(raw, profile, "example.com", (source,)).findings[0].status == "supported"
    text = "Acme – inventory software… built for teams."
    page = source.model_copy(update={"text": text})
    raw["findings"][0]["evidence"][0].update(passage="Acme - inventory software... built for teams.", claim="Sells software.")
    assert validate_extraction(raw, profile, "example.com", (page,)).findings[0].status == "supported"


def test_an_exact_quote_cited_under_another_saved_page_is_re_attributed(example):
    profile, home = example
    text = "Stay ahead with continuous learning through our Partner Academy and AI software certification programs."
    partners = Source(id="partners", url="https://example.com/partners", company_domain="example.com", title="Partners",
                      text=text, content_hash=hashlib.sha256(text.encode()).hexdigest())
    other_text = "Other Co sells AI software to partners through its own academy and certification programs."
    other = Source(id="other", url="https://other.com/", company_domain="other.com", title="Other", text=other_text,
                   content_hash=hashlib.sha256(other_text.encode()).hexdigest())

    def finding(passage, source_id="source-1"):
        return {"name": "Example", "findings": [{"status": "supported", "criterion_id": "ai", "evidence": [{
            "source_id": source_id, "passage": passage, "claim": "Runs a partner academy for its AI software"}]}]}

    rejected = []
    record = validate_extraction(finding(text), profile, "example.com", (home, partners, other), rejected)
    assert record.findings[0].status == "supported" and record.findings[0].evidence[0].source_id == "partners"
    assert record.findings[0].evidence[0].passage == text and not rejected
    # Never re-attributed to another company's page, and a quote on no page is kept for diagnosis only.
    for passage, source_id in ((other_text, "source-1"), ("An academy that appears on none of the saved pages.", "partners")):
        record = validate_extraction(finding(passage, source_id), profile, "example.com", (home, partners, other), rejected)
        assert record.findings[0].status == "unknown"
    assert [item["issue"] for item in rejected] == ["quoted passage could not be found in source"] * 2


def test_identity_is_grounded_in_a_real_line_when_the_quote_is_loose():
    from shortlist.domain import CompanyIdentity
    from shortlist.relevance import ground_identity
    text = "NiCE: Customer Experience (CX) AI Platform\nLogin\nPartners\nNiCE delivers AI across the entire CX journey."
    home = Source(id="home", url="https://www.nice.example/", company_domain="nice.example", title="NiCE", text=text,
                  content_hash=hashlib.sha256(text.encode()).hexdigest())
    loose = CompanyIdentity(name="NiCE", domain="nice.example", source_id="home", passage="NiCE is the CX AI platform company.")
    grounded, issue = ground_identity(loose, (home,), "nice.example")
    assert issue is None and grounded.passage == "NiCE: Customer Experience (CX) AI Platform"
    # A name the page never uses, or one that cannot be tied to the website owner, is still refused.
    for name in ("Acme", "Customer Experience"):
        _, issue = ground_identity(loose.model_copy(update={"name": name}), (home,), "nice.example")
        assert issue is not None, name


def test_exact_quote_from_other_company_rejected(example):
    profile, source = example
    raw = {"name": "Other", "findings": [{"status": "supported", "criterion_id": "ai", "evidence": [{
        "source_id": source.id, "passage": source.text, "claim": "AI software"}]}]}
    assert validate_extraction(raw, profile, "other.com", (source,)).findings[0].status == "unknown"


def test_worker_real_database_flow(tmp_path, example):
    from shortlist.config import Settings
    from shortlist.domain import Review
    from shortlist.export import export_run
    from shortlist.store import Store
    from shortlist.verification import Judgment, Verification, assessments
    from shortlist.worker import execute_run

    profile, source = example
    class FixtureSearch:
        name = "labelled_fixture"
        def search(self, query, seller_url):
            return [Candidate(domain="example.com", name="Example", url=source.url, query=query, provider=self.name)]
    class FixtureModel:
        name = "labelled_fixture"
        def verify(self, profile, record):
            return Verification(judgments=[Judgment(assessment_id=a["assessment_id"], verdict="entailed",
                reason="Labelled synthetic fixture judgment") for a in assessments(profile, record)])

        def research(self, profile, candidate, sources):
            return validate_extraction({"name": "Example", "findings": [{"status": "supported", "criterion_id": "ai",
                "evidence": [{"source_id": source.id, "passage": source.text, "claim": "AI software"}]}]},
                profile, candidate.domain, sources)
    settings = Settings(db_path=tmp_path / "flow.sqlite3")
    store = Store(settings.db_path)
    run_id = store.create_run(profile, "fixture-flow")
    assert execute_run(store, settings, run_id, search=FixtureSearch(), model=FixtureModel(), fetch=lambda *a, **kw: source)
    reopened = Store(settings.db_path)
    run = reopened.get_run(run_id)
    assert run["status"] == "ready"
    assert len(run["records"]) == 1
    assert len(run["attempts"]) == 6  # Three searches (one company is low yield), one fetch, research and verification.
    assert not execute_run(reopened, settings, run_id)
    reopened.review(run_id, run["records"][0]["research"]["id"], Review(decision="accepted"))
    exported = export_run(reopened.get_run(run_id), "json", accepted_only=True)
    assert source.text in exported
    assert "accepted" in exported
    assert "Human acceptance is not buying intent" in exported
