"""Unreadable candidates preserve failures but do not occupy review slots."""
import hashlib
import json

import pytest

from shortlist.config import Settings
from shortlist.domain import Candidate, Criterion, Profile, Source
from shortlist.export import export_run
from shortlist.fetch import FetchError, domain_of
from shortlist.providers import validate_extraction
from shortlist.store import Store
from shortlist.worker import execute_run


@pytest.mark.parametrize("all_fail,crash", [(False, False), (True, False), (False, True)])
def test_bounded_fallback_and_saved_failure_survive_restart(tmp_path, all_fail, crash, monkeypatch):
    store = Store(tmp_path / "fallback.sqlite3")
    settings = Settings(db_path=store.path)
    profile = Profile(seller_url="https://seller.example", offer="Customer acquisition research",
                      target="Business software", criteria=(Criterion(id="software", description="Offers software"),))
    run_id = store.create_run(profile, "fallback")
    fence = store.claim(run_id)
    candidates = [Candidate(domain=f"company-{i}.example", url=f"https://company-{i}.example/",
                            name=f"Labelled fixture {i}", query="fixture", provider="fixture") for i in range(7)]
    store.checkpoint(run_id, fence, "research", {"candidates": [c.model_dump(mode="json") for c in candidates]}, "queued")
    calls = []

    def fetch(url, expected_domain=None):
        domain = domain_of(url)
        calls.append(domain)
        if all_fail or domain in {c.domain for c in candidates[:3]}:
            raise FetchError("Labelled fixture unreadable page")
        text = "Labelled readable fixture with software information."
        return Source(url=url, company_domain=domain, title="Fixture", text=text,
                      content_hash=hashlib.sha256(text.encode()).hexdigest())

    class Model:
        name = "labelled_fixture"

        def research(self, profile, candidate, sources):
            return validate_extraction({"name": candidate.name, "findings": []}, profile, candidate.domain, sources)

    class Crash(BaseException):
        pass

    if crash:
        checkpoint = store.checkpoint

        def stop_after_failure(*args, **kwargs):
            checkpoint(*args, **kwargs)
            if args[3].get("candidate_failures"):
                raise Crash()

        monkeypatch.setattr(store, "checkpoint", stop_after_failure)
        with pytest.raises(Crash):
            execute_run(store, settings, run_id, model=Model(), fetch=fetch)
        with store.connection() as db:
            db.execute("UPDATE runs SET lease_until=0 WHERE id=?", (run_id,))
        store = Store(store.path)
    execute_run(store, settings, run_id, model=Model(), fetch=fetch)
    saved = Store(store.path).get_run(run_id)
    assert calls == [c.domain for c in candidates[:6]]
    assert sum(a["kind"] == "fetch" for a in saved["attempts"]) == 6
    assert len(saved["records"]) == (0 if all_fail else 3)
    assert len(saved["checkpoint"]["candidate_failures"]) == (6 if all_fail else 3)
    assert saved["status"] == "partial"
    if all_fail:
        assert saved["error"] == "No readable company evidence could be collected"
    else:
        assert {r["research"]["domain"] for r in saved["records"]} == {c.domain for c in candidates[3:6]}
        assert all(r["research"]["sources"] for r in saved["records"])
    assert json.loads(export_run(saved, "json"))["candidate_failures"] == saved["checkpoint"]["candidate_failures"]
