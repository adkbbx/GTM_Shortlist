"""Recorded relevance failures plus labelled offline boundary/worker fixtures."""
import hashlib
import json

import httpx
import pytest

from shortlist.config import Settings
from shortlist.domain import Candidate, Criterion, Profile, Source
from shortlist.fetch import domain_of
from shortlist.market import market_candidates
from shortlist.providers import Gemma, candidates_from_results, validate_extraction
from shortlist.relevance import candidate_issue, company_page_issue
from shortlist.store import Store
from shortlist.worker import execute_run


@pytest.mark.parametrize("url,title", [
    ("https://filament.digital/best-b2b-saas-marketing-agencies", "The 10 Best B2B SaaS Marketing Agencies in 2026"),
    ("https://www.datamation.com/cloud/saas-companies", "76 Top SaaS Companies to Know in 2026"),
    ("https://www.highspot.com/go-to-market-guide/revops-leaders/revops-team-maturity-level", "Why CROs Must Elevate Their RevOps Team's Maturity"),
    ("https://growintandem.com/revops-framework", "RevOps Framework: How B2B Companies Unify GTM in 2026"),
    ("https://www.battery.com/blog/the-new-cro-playbook-leading-revenue-teams-in-the-age-of-ai", "The New CRO Playbook"),
    ("https://www.iconiq.com/growth/reports/gtm-org-structure-ai-2026", "Leaner, Smarter, Flatter"),
    ("https://www.11x.ai/tips/revenue-orchestration", "Revenue Orchestration"),
    ("https://reference.example/%62log/company-roundup", "Company roundup"),
])
def test_recorded_editorial_results_are_not_company_identities(url, title):
    assert company_page_issue(url, title)
    assert candidates_from_results([{"url": url, "title": title}], "fixture", "fixture", None) == []


@pytest.mark.parametrize("url,title", [
    ("https://company.example/", "The best software for your team"),
    ("https://company.example/products/report-builder", "Report Builder"),
    ("https://company.example/solutions/risk-framework", "Risk Framework"),
    ("https://company.example/services", "Manufacturing consulting"),
    ("https://company.example/about", "Our company"),
    ("https://company.example/platform", "Our platform"),
])
def test_home_product_service_and_about_pages_are_preserved(url, title):
    assert company_page_issue(url, title) is None


def test_article_cannot_hide_later_official_result_on_the_same_domain():
    hits = [{"url": "https://company.example/blog/topic", "title": "Topic"},
            {"url": "https://company.example/", "title": "Company"}]
    candidates = candidates_from_results(hits, "fixture", "fixture", None)
    assert [candidate.url for candidate in candidates] == ["https://company.example/"]
    assert market_candidates(candidates, "https://seller.example") == candidates
    article = candidates[0].model_copy(update={"url": hits[0]["url"]})
    assert market_candidates([article], "https://seller.example") == []


def test_reference_results_cannot_enter_through_saved_or_custom_searches():
    for domain in ("en.wikipedia.org", "www.definitions.net", "www.vocabulary.com"):
        assert candidate_issue(Candidate(domain=domain, name="Leading", url=f"https://{domain}/",
                                         query="fixture", provider="fixture"))


def source(url, title="Labelled company homepage"):
    text = "Labelled manufacturer operates multiple production locations."
    return Source(url=url, company_domain=domain_of(url), title=title, text=text,
                  content_hash=hashlib.sha256(text.encode()).hexdigest())


@pytest.mark.parametrize("selection_policy", [None, 3])
def test_worker_skips_articles_and_redirected_editorial_pages_without_model_calls(tmp_path, selection_policy):
    settings = Settings(db_path=tmp_path / "relevance.sqlite3")
    store = Store(settings.db_path)
    profile = Profile(seller_url="https://seller.example", offer="Equipment for manufacturing plants",
                      target="Manufacturing companies", criteria=(Criterion(id="plant", description="Operates manufacturing plants"),))
    identity = store.create_run(profile, "labelled-relevance")
    candidates = [Candidate(domain=f"company-{i}.example", name="Labelled company",
                            url=f"https://company-{i}.example/" + ("blog/industry" if i == 0 else ""),
                            query="fixture", provider="fixture") for i in range(5)]
    fence = store.claim(identity)
    checkpoint = {"candidates": [c.model_dump(mode="json") for c in candidates], "company_limit": 3}
    if selection_policy:
        checkpoint["selection_policy"] = selection_policy
    store.checkpoint(identity, fence, "research", checkpoint, "queued")
    fetched, researched = [], []

    def fetch(url, expected_domain=None):
        fetched.append(url)
        # A company-looking search URL redirected to an article; reject after one fetch.
        return source(url + "blog/industry" if expected_domain == "company-1.example" else url)

    class Model:
        name = "labelled_fixture"

        def research(self, profile, candidate, sources):
            researched.append(candidate.domain)
            return validate_extraction({"name": "Labelled manufacturer", "findings": []}, profile, candidate.domain, sources)

    execute_run(store, settings, identity, model=Model(), fetch=fetch)
    saved = store.get_run(identity)
    assert len(saved["records"]) == 3
    assert researched == [c.domain for c in candidates[2:]]
    assert len(fetched) == 4 and not any("company-0" in url for url in fetched)
    assert set(saved["checkpoint"]["candidate_failures"]) == {c.domain for c in candidates[:2]}
    assert all("Article" in failure["reason"] for failure in saved["checkpoint"]["candidate_failures"].values())
    assert not execute_run(store, settings, identity, model=Model(), fetch=fetch)
    assert len(fetched) == 4  # No retry, extra search or repeated model work.


def test_direct_model_replay_refuses_article_before_inference(monkeypatch):
    def refuse(*args, **kwargs):
        raise AssertionError("No network or model call permitted")
    monkeypatch.setattr(httpx, "Client", refuse)
    candidate = Candidate(domain="publisher.example", name="Industry article", url="https://publisher.example/blog/topic",
                          query="fixture", provider="fixture")
    profile = Profile(seller_url="https://seller.example", offer="Equipment for manufacturing plants",
                      target="Manufacturers", criteria=(Criterion(id="plant", description="Operates manufacturing plants"),))
    with pytest.raises(ValueError, match="Article"):
        Gemma(Settings()).research(profile, candidate, (source(candidate.url),))


def test_saved_editorial_source_is_rejected_before_followups_or_inference(tmp_path):
    settings = Settings(db_path=tmp_path / "cached-article.sqlite3")
    store = Store(settings.db_path)
    profile = Profile(seller_url="https://seller.example", offer="Equipment for manufacturing plants",
                      target="Manufacturers", criteria=(Criterion(id="plant", description="Operates manufacturing plants"),))
    identity = store.create_run(profile, "cached-article")
    fence = store.claim(identity)
    candidate = Candidate(domain="publisher.example", name="Publisher", url="https://publisher.example/",
                          query="fixture", provider="fixture")
    article = source("https://publisher.example/blog/industry").model_copy(update={
        "activity_links": ("https://publisher.example/news/new-post",),
        "research_links": ("https://publisher.example/about",)})
    store.checkpoint(identity, fence, "research", {"selection_policy": 3,
        "candidates": [candidate.model_dump(mode="json")],
        "sources": {candidate.domain: [article.model_dump(mode="json")]}}, "queued")

    class NoModel:
        name = "fixture"

        def research(self, *args):
            raise AssertionError("Rejected source must not trigger inference")

    def no_fetch(*args, **kwargs):
        raise AssertionError("Rejected source must not trigger follow-up fetches")

    execute_run(store, settings, identity, model=NoModel(), fetch=no_fetch)
    saved = store.get_run(identity)
    assert not saved["records"] and not saved["attempts"]
    assert candidate.domain in saved["checkpoint"]["candidate_failures"]


BUYER = {"seller_offer": "Payroll software for distributed employers", "target_customer": "Multi-location employers",
         "customer_criteria": [{"id": "locations", "subject": "target_customer",
                                "customer_characteristic": "Operates multiple business locations", "required": True}],
         "unknowns": ["Employee count is not established"]}


@pytest.mark.parametrize("compact", [False, True])
def test_new_seller_format_separates_offer_from_customer_and_saves_existing_contract(monkeypatch, compact):
    from shortlist.prompting import Runtime
    requests = []
    original = httpx.Client

    def response(request):
        requests.append(json.loads(request.content))
        return httpx.Response(200, json={"choices": [{"message": {"tool_calls": [{"type": "function",
            "function": {"name": "submit_seller_summary", "arguments": json.dumps(BUYER)}}]}, "finish_reason": "tool_calls"}]})
    monkeypatch.setattr(httpx, "Client", lambda **kwargs: original(transport=httpx.MockTransport(response), **kwargs))
    model = Gemma(Settings(gemma_base_url="https://model.example/v1", gemma_model="fixture"))
    model._runtime = Runtime(profile="compact" if compact else "full", ollama=False)
    draft = model.seller(source("https://seller.example/"))
    assert draft.offer == BUYER["seller_offer"] and draft.target == BUYER["target_customer"]
    assert draft.criteria[0].description == "Operates multiple business locations"
    assert len(requests) == 1
    payload = requests[0]
    schema = payload["tools"][0]["function"]["parameters"]
    assert set(schema["properties"]) == {"seller_offer", "target_customer", "customer_criteria", "unknowns"}
    assert schema["properties"]["customer_criteria"]["items"]["properties"]["subject"]["const"] == "target_customer"
    assert "not other equipment vendors" in payload["messages"][0]["content"]
    assert "seller_page_text" in payload["messages"][1]["content"]


@pytest.mark.parametrize("changes", [
    {"subject": "seller"},
    {"customer_characteristic": "The platform integrates with multiple CRMs"},
    {"customer_characteristic": "Trusted by 500,000 customers"},
    {"customer_characteristic": "Needs help with low lead quality"},
])
def test_new_seller_format_removes_wrong_subject_and_seller_marketing_without_losing_summary(monkeypatch, changes):
    model = Gemma(Settings())
    monkeypatch.setattr(model, "complete", lambda *args, **kwargs: {
        **BUYER, "customer_criteria": [{**BUYER["customer_criteria"][0], **changes}]})
    monkeypatch.setattr(type(model), "compact", property(lambda self: False))
    recovered = model.seller(source("https://seller.example/"))
    assert recovered.offer == BUYER["seller_offer"]
    assert recovered.target == BUYER["target_customer"]
    assert recovered.criteria == [] and len(recovered.criteria_issues) == 1


def test_campaigns_cannot_reintroduce_seller_marketing_as_customer_criteria():
    from shortlist.market import Campaign, CampaignPlan, read_campaign_plan
    campaign = Campaign(name="Labelled buyer segment", target="Manufacturing companies",
                        rationale="Maintenance equipment supports manufacturing facilities",
                        criteria=(Criterion(id="factory", description="Operates manufacturing facilities"),
                                  Criterion(id="seller", description="The platform integrates with every CRM")))
    seller_only = campaign.model_copy(update={"name": "Seller copy", "criteria": (campaign.criteria[1],)})
    plan = read_campaign_plan(CampaignPlan(campaigns=(campaign, seller_only)))
    assert len(plan.campaigns) == 1 and [c.id for c in plan.campaigns[0].criteria] == ["factory"]
    assert any("Seller marketing" in issue for issue in plan.issues)
    assert read_campaign_plan(plan) == plan
