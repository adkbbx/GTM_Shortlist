"""Labelled synthetic providers for browser tests of the real API/worker/database.

Never use this as the live application server. It performs no company discovery.
"""
import hashlib
import os
import threading
import time
from pathlib import Path

import uvicorn

from shortlist.api import create_app
from shortlist.config import Settings
from shortlist.domain import Candidate, Criterion, Source
from shortlist.providers import SellerDraft, validate_extraction
from shortlist.store import Store
from shortlist.verification import Judgment, Verification, assessments
from shortlist.worker import execute_run

settings = Settings(db_path=Path(os.environ.get("SHORTLIST_UI_TEST_DB", "data/ui-test.sqlite3")),
                    tavily_key="labelled_fixture_not_a_real_key", gemma_base_url="https://labelled-fixture.example",
                    gemma_model="labelled_fixture")
store = Store(settings.db_path)


class FixtureSearch:
    name = "labelled_test_fixture"

    def search(self, query, seller_url):
        return [Candidate(domain=f"example-{index}.com", name=f"Example {index} (test fixture)",
                          url=f"https://example-{index}.com/", query=query, provider=self.name)
                for index in (1, 2)]


def fixture_fetch(url, expected_domain=None):
    time.sleep(.15)  # Observable test-provider work, not a simulated UI progress timer.
    text = ("TEST FIXTURE. This is synthetic test content, not a real company. "
            "We provide artificial intelligence software for business operations as a hosted subscription. "
            "Example Labs is a privately held startup. No buying intent has been observed.")
    if expected_domain == "example-1.com":
        text += " Example Labs is headquartered in Canada."
    links = (f"https://{expected_domain}/about", f"https://{expected_domain}/pricing") if expected_domain and url.endswith("/") else ()
    return Source(url=url, company_domain=expected_domain or "eygentic.com", title="Labelled test source",
                  text=text, content_hash=hashlib.sha256(text.encode()).hexdigest(), research_links=links)


class FixtureModel:
    name = "labelled_test_fixture"

    def seller(self, source):
        return SellerDraft(offer="Test fixture: customer acquisition experiments for software businesses",
                           target="Private AI B2B SaaS startups", criteria=[
                               Criterion(id="ai", description="Offers AI software to businesses"),
                               Criterion(id="private", description="Privately held startup")], unknowns=[])

    def verify(self, profile, record):
        time.sleep(.2)
        return Verification(judgments=[Judgment(assessment_id=a["assessment_id"], verdict="entailed",
            reason="Labelled synthetic fixture judgment") for a in assessments(profile, record)])

    def research(self, profile, candidate, sources):
        time.sleep(.5)
        findings = []
        for criterion in profile.criteria:
            if candidate.domain == "example-2.com" and criterion.id == "private":
                findings.append({"criterion_id": criterion.id, "status": "unknown",
                                 "reason": "Test fixture: ownership needs an independent dated source"})
            else:
                passage = "Example Labs is a privately held startup." if criterion.id == "private" else "We provide artificial intelligence software for business operations as a hosted subscription."
                findings.append({"criterion_id": criterion.id, "status": "supported", "evidence": [{
                    "source_id": sources[1].id if criterion.id == "private" else sources[0].id, "passage": passage,
                    "claim": "Test fixture observation from supplied text"}]})
        exclusion_findings = []
        for index, _ in enumerate(profile.exclusions):
            if candidate.domain == "example-1.com":
                passage = "Example Labs is headquartered in Canada." if index == 0 else "Example Labs is a privately held startup."
                exclusion_findings.append({"exclusion_id": f"exclude-{index + 1}", "status": "matched" if index == 0 else "cleared",
                                          "evidence": [{"source_id": sources[0].id, "passage": passage,
                                                        "claim": "Test fixture exclusion assessment"}]})
            else:
                exclusion_findings.append({"exclusion_id": f"exclude-{index + 1}", "status": "unknown",
                                           "reason": "Test fixture: no independent current evidence to assess this exclusion"})
        return validate_extraction({"name": f"Example research company {candidate.domain} (test fixture)",
                                    "findings": findings, "exclusion_findings": exclusion_findings, "hypotheses": [{
                                        "text": "Test fixture: acquisition experiments might be relevant",
                                        "assumptions": ["No need or buying intent has been established"]}]},
                                   profile, candidate.domain, sources)


def loop():
    while True:
        store.worker_heartbeat("labelled_browser_fixture")
        for run in store.list_runs():
            if run["status"] in ("queued", "running"):
                execute_run(store, settings, run["id"], search=FixtureSearch(), model=FixtureModel(), fetch=fixture_fetch)
        time.sleep(.1)


if __name__ == "__main__":
    threading.Thread(target=loop, daemon=True).start()
    uvicorn.run(create_app(settings), host="127.0.0.1", port=8015, log_level="warning")
