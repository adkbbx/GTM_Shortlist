from datetime import UTC, datetime

from shortlist.domain import Candidate, Criterion, Profile
from shortlist.providers import candidates_from_results
from shortlist.selection import prioritize


def candidate(domain, excerpt):
    return Candidate(domain=domain, name=domain, url=f"https://{domain}/", query="fixture",
                     provider="labelled_fixture", excerpt=excerpt, discovered_at=datetime(2026, 10, 15, tzinfo=UTC))


def test_target_relevance_precedes_signals_and_ties_preserve_search_order():
    profile = Profile(seller_url="https://seller.example/", offer="Growth experiments for companies",
                      target="AI logistics software", criteria=(Criterion(id="ai", description="Offers AI software"),))
    inputs = [candidate("unrelated.example", "We are hiring a chef. We raised $5M."),
              candidate("plain.example", "AI logistics software."),
              candidate("event.example", "AI logistics software. We are hiring a sales manager."),
              candidate("tie.example", "AI logistics software. We are hiring a marketer.")]
    ranked, reasons = prioritize(profile, inputs)
    assert [c.domain for c in ranked] == ["event.example", "tie.example", "plain.example", "unrelated.example"]
    assert reasons[0].clues[0].passage == "We are hiring a sales manager."
    assert reasons[0].clues[0].source_url == inputs[2].url
    assert reasons[0].clues[0].observed_at == inputs[2].discovered_at
    assert reasons[0].target_terms == ("ai", "logistics", "software")
    assert reasons[-1].target_terms == ()


def test_negation_missing_snippets_and_duplicate_events_do_not_boost():
    profile = Profile(seller_url="https://seller.example/", offer="Growth experiments for companies",
                      target="software", criteria=(Criterion(id="software", description="Offers software"),))
    inputs = [candidate("negative.example", "Software. We are not hiring a developer. No seed funding."),
              candidate("empty.example", ""),
              candidate("repeat.example", "Software. We are hiring a developer. We are hiring a developer.")]
    _, reasons = prioritize(profile, inputs)
    by_domain = {r.domain: r for r in reasons}
    assert by_domain["negative.example"].clues == ()
    assert len(by_domain["repeat.example"].clues) == 1
    assert by_domain["empty.example"].target_terms == ()


def test_both_search_adapters_retain_bounded_exact_excerpts():
    hits = [{"url": "https://alpha.example", "title": "Alpha", "content": "Exact Tavily passage."},
            {"link": "https://beta.example", "title": "Beta", "snippet": "Exact SerpApi passage."},
            {"url": "https://long.example", "snippet": "x" * 4000}]
    candidates = candidates_from_results(hits, "fixture", "fixture", "https://seller.example")
    assert [c.excerpt for c in candidates] == ["Exact Tavily passage.", "Exact SerpApi passage.", "x" * 3000]


def test_discussion_posts_are_not_mistaken_for_companies_but_company_homepage_is_allowed():
    hits = [{"url": "https://www.reddit.com/r/ProductMarketing/comments/example/", "title": "An ICP discussion"},
            {"url": "https://www.reddit.com/", "title": "Reddit company homepage"}]
    results = candidates_from_results(hits, "fixture", "fixture", "https://seller.example/")
    assert [c.url for c in results] == ["https://www.reddit.com/"]


def test_worker_researches_ranked_candidates_and_preserves_selection(tmp_path):
    import hashlib

    from shortlist.config import Settings
    from shortlist.domain import Source
    from shortlist.providers import validate_extraction
    from shortlist.store import Store
    from shortlist.worker import execute_run

    profile = Profile(seller_url="https://seller.example/", offer="Growth experiments for companies",
                      target="logistics software", criteria=(Criterion(id="software", description="Offers software"),))
    inputs = [candidate(f"low-{i}.example", "Unrelated restaurant") for i in range(3)]
    inputs += [candidate(f"match-{i}.example", "Logistics software. We are hiring a marketer.") for i in range(3)]

    class Search:
        name = "labelled_fixture"

        def search(self, query, seller_url):
            return inputs

    class Model:
        name = "labelled_fixture"

        def research(self, profile, candidate, sources):
            return validate_extraction({"name": candidate.name, "findings": []}, profile, candidate.domain, sources)

    fetched = []

    def fetch(url, expected_domain=None):
        fetched.append(expected_domain)
        text = "Labelled fixture page."
        return Source(url=url, company_domain=expected_domain, title="Fixture", text=text,
                      content_hash=hashlib.sha256(text.encode()).hexdigest())

    settings = Settings(db_path=tmp_path / "ranked.sqlite3")
    store = Store(settings.db_path)
    identity = store.create_run(profile, "ranked-worker")
    execute_run(store, settings, identity, search=Search(), model=Model(), fetch=fetch)
    saved = Store(store.path).get_run(identity)
    assert fetched == [f"match-{i}.example" for i in range(3)]
    assert [r["research"]["domain"] for r in saved["records"]] == fetched
    assert saved["checkpoint"]["selection"][0]["clues"][0]["passage"] == "We are hiring a marketer."
    from fastapi.testclient import TestClient

    from shortlist.api import create_app
    response = TestClient(create_app(settings)).get(f"/api/runs/{identity}")
    assert response.status_code == 200
    assert response.json()["selection"] == saved["checkpoint"]["selection"]
    assert not execute_run(Store(store.path), settings, identity, search=Search(), model=Model(), fetch=fetch)
    assert len(fetched) == 3
