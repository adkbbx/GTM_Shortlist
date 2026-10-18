"""scripts/replay_saved_runs.py on a small saved database shaped like the real ones: a list page researched as a company,
the same company researched twice for one seller, and a lead held back only by checks a website rarely states."""
import hashlib
import importlib.util
from pathlib import Path

from shortlist.domain import Candidate, Criterion, Profile, Source
from shortlist.providers import validate_extraction
from shortlist.store import Store

ROOT = Path(__file__).resolve().parents[1]
TEXT = "Labelled fixture page. We sell AI software to businesses as a hosted subscription."


def replay_module():
    spec = importlib.util.spec_from_file_location("replay_saved_runs", ROOT / "scripts/replay_saved_runs.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def saved_run(store, key, companies):
    profile = Profile(seller_url="https://seller.example/", offer="Customer acquisition research", target="Private AI B2B SaaS startups",
                      criteria=(Criterion(id="ai", description="Offers AI software to businesses"),
                                Criterion(id="private", description="Privately held startup")),
                      exclusions=("Consultancies without a software product", "Publicly listed companies"))
    run_id = store.create_run(profile, key)
    fence = store.claim(run_id)
    saved_profile = Profile.model_validate(store.get_run(run_id)["profile"])
    candidates = []
    for domain, url, title in companies:
        source = Source(url=url, company_domain=domain, title=title, text=TEXT, content_hash=hashlib.sha256(TEXT.encode()).hexdigest())
        candidates.append(Candidate(domain=domain, url=url, name=title, query="fixture", provider="fixture"))
        record = validate_extraction({
            "name": title, "findings": [
                {"criterion_id": "ai", "status": "supported", "evidence": [
                    {"source_id": source.id, "passage": "We sell AI software to businesses as a hosted subscription.", "claim": "Labelled"}]},
                {"criterion_id": "private", "status": "unknown", "reason": "Labelled: ownership is not stated"}],
            "exclusion_findings": [
                {"exclusion_id": "exclude-1", "status": "cleared", "evidence": [
                    {"source_id": source.id, "passage": "We sell AI software to businesses as a hosted subscription.", "claim": "Labelled"}]},
                {"exclusion_id": "exclude-2", "status": "unknown", "reason": "Labelled: listing status is not stated"}],
        }, saved_profile, domain, (source,))
        # Saved runs predate today's page gates; a list page saved then is inserted as it was, not through them.
        with store.connection() as db:
            db.execute("INSERT INTO records(id,run_id,domain,research) VALUES (?,?,?,?)",
                       (record.id, run_id, record.domain, record.model_dump_json()))
    checkpoint = store.get_run(run_id)["checkpoint"]
    store.checkpoint(run_id, fence, "review", {**checkpoint, "candidates": [c.model_dump(mode="json") for c in candidates]}, "partial")
    return run_id


def test_replay_counts_saved_credits_and_leads_qualified_from_the_same_evidence(tmp_path):
    store = Store(tmp_path / "saved.sqlite3")
    saved_run(store, "first", [("labelled-ai.example", "https://labelled-ai.example/", "Labelled AI | Software for businesses"),
                               ("lists.example", "https://lists.example/blog/top-ai-startups", "Top 25 AI startups")])
    saved_run(store, "second", [("labelled-ai.example", "https://labelled-ai.example/", "Labelled AI | Software for businesses")])
    report = replay_module().replay(str(store.path))
    assert report["totals"]["records"] == 3
    assert report["totals"]["qualified_before:needs_verification"] == 3
    # Ownership and listing status asked in conversation: the verified AI evidence and cleared exclusion make fits.
    assert report["totals"]["qualified_after_advice:fits"] == 3
    assert report["totals"]["credits_saved:not_a_company_page"] == 1
    assert report["totals"]["credits_saved:repeat"] == 1
    first = report["runs"][0]
    assert first["first_lead"] == "labelled-ai.example"
    assert "exclusion: Publicly listed companies" in first["advised"] and "Privately held startup" in first["advised"]
