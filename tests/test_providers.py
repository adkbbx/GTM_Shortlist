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
    assert len(run["attempts"]) == 5
    assert not execute_run(reopened, settings, run_id)
    reopened.review(run_id, run["records"][0]["research"]["id"], Review(decision="accepted"))
    exported = export_run(reopened.get_run(run_id), "json", accepted_only=True)
    assert source.text in exported
    assert "accepted" in exported
    assert "Human acceptance is not buying intent" in exported
