"""Discovery policy 2: compact company queries, stricter admission, research from a company's own entry page and a
wider research range. Measured against labelled real search results in examples/evaluation/discovery-admission.json."""
import hashlib
import importlib.util
from pathlib import Path

import pytest

from shortlist.config import Settings
from shortlist.domain import Candidate, Criterion, Profile, Source
from shortlist.fetch import FetchError, domain_of
from shortlist.providers import queries_for, search_phrase, validate_extraction
from shortlist.relevance import candidate_issue, company_page_issue, research_entry
from shortlist.store import RUN_CAPS, Store
from shortlist.worker import execute_run

ROOT = Path(__file__).resolve().parents[1]


def evaluator():
    spec = importlib.util.spec_from_file_location("evaluate_discovery", ROOT / "scripts/evaluate_discovery.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_labelled_real_search_results_reach_research_only_as_company_pages():
    report = evaluator().evaluate(policy=2)
    assert report["companies_reaching_research"] == "21 of 21"
    assert int(report["non_companies_reaching_research"].split()[0]) <= 3
    assert report["fetches_wasted_on_rejected_pages"] == 0
    # Without entry pages, real companies found through deep product pages were fetched and then refused.
    assert evaluator().evaluate(policy=1)["companies_reaching_research"] == "16 of 21"


@pytest.mark.parametrize("target,phrase", [
    ("Private AI B2B SaaS startups", "Private AI B2B SaaS startups"),
    (("B2B and SaaS companies of any size or stage, including specialized business software, seeking more predictable "
     "customer acquisition and evidence-based growth rather than volume-based activity."), "B2B SaaS"),
    ("Seed to Series A B2B SaaS companies with a launched product.", "B2B SaaS"),
    ("Global Brands and Advertisers seeking to scale their marketing efforts through affiliate partnerships.",
     "Global Brands Advertisers marketing affiliate partnerships"),
    (("Sales and Marketing Operations teams within technology companies focused on optimizing their Go-To-Market (GTM) "
     "processes and revenue generation."), "technology companies"),
    (("Companies managing and scaling channel partner programs, from emerging to enterprise levels, that require tools to "
     "manage partner onboarding, co-selling, co-marketing, and performance tracking."), "channel partner programs"),
    ("Large enterprises with established, complex channel partner ecosystems (100+ partners) requiring governance.",
     "Large enterprises channel partner ecosystems"),
    ("Independent coffee roasters that sell wholesale to cafes", "Independent coffee roasters"),
    ("global e-commerce", "global e-commerce"),
])
def test_saved_targets_become_short_company_phrases(target, phrase):
    assert search_phrase(target) == phrase


def test_policy_two_asks_for_companies_own_pages_and_policy_one_is_unchanged():
    profile = Profile(seller_url="https://seller.example/", offer="Customer acquisition experiments for software companies",
                      target="B2B and SaaS companies of any size or stage, seeking predictable growth",
                      criteria=(Criterion(id="software", description="Sells software to businesses"),))
    assert queries_for(profile, policy=2) == (
        "B2B SaaS company official website", "B2B SaaS company pricing", "B2B SaaS company about us")
    assert queries_for(profile, "Dental clinics in Ontario", policy=2) == (
        "Dental clinics Ontario company official website", "Dental clinics Ontario company about us",
        "Dental clinics Ontario company products services")
    assert queries_for(profile) == (f"{profile.target} software company official website", f"{profile.target} startup platform pricing")
    assert queries_for(profile, "global e-commerce") == (
        "global e-commerce company official website", "global e-commerce company (hiring OR expansion OR launch OR funding) official")


def candidate(url, title="Labelled fixture", query="B2B SaaS company official website"):
    return Candidate(domain=domain_of(url), url=url, name=title, query=query, provider="fixture")


@pytest.mark.parametrize("url", [
    "https://www.youtube.com/watch?v=OjR_1N9Snf4", "https://www.indeed.com/q-lead-generation-l-remote-jobs.html",
    "https://www.gartner.com/reviews/market/partner-relationship-management-applications",
    "https://www.vcbacked.co/directory/funding/seed/industry/saas", "https://startup.jobs/head-of-revenue-operations-1",
])
def test_video_job_review_and_startup_database_sites_are_refused_before_any_fetch(url):
    assert "Video, social" in candidate_issue(candidate(url, "Labelled saved search result"))


def test_public_sector_sites_are_candidates_only_for_public_sector_searches():
    county = "https://www.labelledcounty.gov/"
    assert "Public-sector" in candidate_issue(candidate(county, "Home - Labelled County"))
    assert candidate_issue(candidate(county, "Home - Labelled County", "county government agencies company official website")) is None
    assert "Public-sector" in candidate_issue(candidate("https://data.labelled.europa.eu/", "Data portal"))


def test_filtered_listings_lists_and_reports_are_refused_but_company_titles_are_not():
    assert "Filtered listing" in candidate_issue(candidate("https://startups.example/?industries=SaaS", "Top Startups"))
    assert candidate_issue(candidate("https://acme.example/?utm_source=search", "Acme | Inventory software")) is None
    for title in ("25,000+ Funded B2B SaaS Startups 2026", "16 of the Best Affiliate Marketing Websites for 2026",
                  "3,529 SaaS Seed Startups (October 2026)", "B2B SaaS Market Size, Share Analysis, Growth Report",
                  "Affiliate Marketing Market 2026–2035 | Analysis"):
        assert company_page_issue("https://publisher.example/lists/saas", title) is not None, title
    # A homepage is never refused for a count in its own title.
    assert company_page_issue("https://acme.example/", "Acme | Trusted by 500+ teams") is None
    assert company_page_issue("https://acme.example/", "24 Hour Labelled Fitness") is None
    for url in ("https://blog.engineer.example/i-replaced-a-tool", "https://publisher.example/post/guide-to-prm",
                "https://nist.example/glossary/term/saas", "https://acme.example/blog-posts/five-agencies"):
        assert company_page_issue(url, "Labelled") is not None, url


def test_research_starts_from_the_homepage_of_a_company_found_on_a_deep_page():
    assert research_entry("https://impact.com/partners/affiliate-partners", "Affiliate Partner Marketplace - impact.com") == "https://impact.com/"
    assert research_entry("https://www.salesforce.com/sales/partner-relationship-management/software") == "https://www.salesforce.com/"
    for url in ("https://acme.example/", "https://acme.example/pricing", "https://acme.example/en", "https://acme.example/about"):
        assert research_entry(url) == url
    # Content pages are refused at admission, so they are never redirected to a homepage here.
    assert research_entry("https://acme.example/blog/our-guide") == "https://acme.example/blog/our-guide"


class Model:
    name = "labelled_fixture"

    def __init__(self):
        self.calls = 0

    def research(self, profile, candidate, sources):
        self.calls += 1
        return validate_extraction({"name": candidate.name, "findings": []}, profile, candidate.domain, sources)


def readable(fetched, unreadable=()):
    def fetch(url, expected_domain=None):
        domain = domain_of(url)
        fetched.append(url)
        if domain in unreadable:
            raise FetchError("Labelled fixture unreadable page")
        text = "Labelled readable fixture with software information."
        return Source(url=url, company_domain=domain, title="Labelled fixture", text=text,
                      content_hash=hashlib.sha256(text.encode()).hexdigest())
    return fetch


def research_run(tmp_path, candidates):
    store = Store(tmp_path / "policy.sqlite3")
    profile = Profile(seller_url="https://seller.example", offer="Customer acquisition research", target="Business software",
                      criteria=(Criterion(id="software", description="Offers software"),))
    run_id = store.create_run(profile, "policy-two")
    assert store.get_run(run_id)["checkpoint"]["discovery_policy"] == 2  # New runs use the new discovery behaviour.
    fence = store.claim(run_id)
    store.checkpoint(run_id, fence, "research", {"discovery_policy": 2, "company_identity_policy": 1,
                                                 "candidates": [c.model_dump(mode="json") for c in candidates]}, "queued")
    with store.connection() as db:
        db.execute("UPDATE runs SET lease_until=0 WHERE id=?", (run_id,))
    return store, run_id


def companies(count, deep_first=False):
    return [Candidate(domain=f"company-{i}.example", name=f"Labelled fixture {i}", query="fixture", provider="fixture",
                      url=f"https://company-{i}.example/" + ("partners/program" if deep_first and i == 0 else ""))
            for i in range(count)]


def test_research_continues_past_six_rejected_candidates_and_starts_from_entry_pages(tmp_path):
    found = companies(9, deep_first=True)
    store, run_id = research_run(tmp_path, found)
    fetched = []
    execute_run(store, Settings(db_path=store.path), run_id, model=Model(),
                fetch=readable(fetched, unreadable={f"company-{i}.example" for i in range(1, 6)}))
    saved = store.get_run(run_id)
    assert fetched[0] == "https://company-0.example/"  # Not the partner page the identity check would refuse.
    assert {r["research"]["domain"] for r in saved["records"]} == {"company-0.example", "company-6.example", "company-7.example"}
    assert "company-8.example" not in {domain_of(url) for url in fetched}  # Stops once the batch is complete.


def test_research_stops_cleanly_at_the_runs_model_limit(tmp_path, monkeypatch):
    monkeypatch.setitem(RUN_CAPS, "model", 3)
    store, run_id = research_run(tmp_path, companies(5))
    model = Model()
    execute_run(store, Settings(db_path=store.path), run_id, model=model, fetch=readable([]))
    saved = store.get_run(run_id)
    assert len(saved["records"]) == 2 and model.calls == 2
    assert saved["status"] == "partial"
    assert saved["error"].startswith("Research stopped at this run's provider limit with 2 of 3 companies")
