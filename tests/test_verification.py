"""Gate mechanics on semantic labels; actual model accuracy is measured separately."""
import json
from pathlib import Path

import pytest

from shortlist.config import Settings
from shortlist.domain import Candidate
from shortlist.evaluation import semantic_case
from shortlist.providers import ProviderError
from shortlist.store import Store
from shortlist.verification import (
    Judgment,
    Verification,
    apply_verification,
    assessments,
    unavailable,
)
from shortlist.worker import execute_run

CASES = json.loads((Path(__file__).parents[1] / "examples/evaluation/semantic-cases.json").read_text())


@pytest.mark.parametrize("case", CASES, ids=lambda c: c["id"])
def test_gate_projects_labelled_judgment_without_changing_evidence(case):
    profile, proposed = semantic_case(case)
    identity = assessments(profile, proposed)[0]["assessment_id"]
    audit = Verification(judgments=[Judgment(assessment_id=identity,
        verdict="entailed" if case["expected_entailed"] else "unsupported", reason=case["rationale"])])
    final = apply_verification(profile, proposed, audit)
    result = final.exclusion_findings[0] if case["kind"] == "exclusion" else final.findings[0]
    assert (result.status != "unknown") == case["expected_entailed"]
    assert final.sources == proposed.sources
    assert final.id == proposed.id
    assert proposed.model_dump() != final.model_dump() or case["expected_entailed"]


def test_missing_and_unavailable_judgments_fail_closed():
    profile, proposed = semantic_case(CASES[0])
    final = apply_verification(profile, proposed, Verification(judgments=[]))
    assert final.findings[0].status == "unknown"
    assert final.qualification == "needs_verification"
    assert "missing" in final.unknowns[0]
    failed = unavailable(profile, proposed, "Verification endpoint is unavailable")
    assert failed.findings[0].status == "unknown"
    assert failed.sources == proposed.sources


@pytest.mark.parametrize("ids", [("criterion:invented",), ("criterion:check", "criterion:check")])
def test_invented_and_duplicate_judgment_ids_rejected(ids):
    profile, proposed = semantic_case(CASES[0])
    with pytest.raises(ValueError, match="unknown or duplicate"):
        apply_verification(profile, proposed, Verification(judgments=[
            Judgment(assessment_id=i, verdict="entailed", reason="Labelled fixture") for i in ids]))


@pytest.mark.parametrize("budget", [False, True])
def test_worker_verification_failure_or_budget_preserves_sources_as_unknown(tmp_path, budget):
    profile, proposed = semantic_case(CASES[0])
    store = Store(tmp_path / "verify.sqlite3")
    settings = Settings(db_path=store.path)
    run_id = store.create_run(profile, "verify-fixture")
    fence = store.claim(run_id)
    candidate = Candidate(domain=proposed.domain, url=proposed.sources[0].url, name=proposed.name,
                          query="Labelled fixture", provider="fixture")
    checkpoint = {"candidates": [candidate.model_dump(mode="json")],
                  "sources": {proposed.domain: [s.model_dump(mode="json") for s in proposed.sources]}}
    if budget:
        for i in range(7):
            attempt = store.reserve(run_id, fence, "fixture", "model", f"prior:{i}")
            store.outcome(attempt, "failed", run_id=run_id, fence=fence)
    store.checkpoint(run_id, fence, "research", checkpoint, "queued")

    class Model:
        name = "labelled_fixture"
        calls = 0

        def research(self, profile, candidate, sources):
            return proposed

        def verify(self, profile, record):
            self.calls += 1
            raise ProviderError("Labelled verification outage")

    model = Model()
    execute_run(store, settings, run_id, model=model)
    saved = Store(store.path).get_run(run_id)
    record = saved["records"][0]["research"]
    assert record["findings"][0]["status"] == "unknown"
    assert record["sources"][0]["text"] == proposed.sources[0].text
    assert saved["status"] == "partial"
    assert model.calls == (0 if budget else 1)
    assert len(saved["attempts"]) == (8 if budget else 2)
