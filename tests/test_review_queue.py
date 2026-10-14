import json

from shortlist.config import Settings
from shortlist.domain import Criterion, Profile, Research, Review
from shortlist.review_queue import review_queue
from shortlist.store import Store


def test_operator_triage_is_read_only_and_customer_acceptance_is_separate(tmp_path, monkeypatch, capsys):
    from shortlist.cli import main
    settings = Settings(db_path=tmp_path / "queue.sqlite3")
    store = Store(settings.db_path)
    profile = Profile(seller_url="https://seller.example/", offer="Labelled research service",
                      target="Business software", criteria=(Criterion(id="software", description="Offers software"),))
    identity = store.create_run(profile, "queue-fixture")
    fence = store.claim(identity)
    research = Research(domain="company.example", name="Labelled triage fixture", profile_id=profile.id,
                        findings=(), sources=(), qualification="needs_verification", status="partial",
                        unknowns=("No readable sources were available in this fixture",))
    store.save_record(identity, fence, research, billable=False)
    store.checkpoint(identity, fence, "complete", {}, "partial")
    before = store.get_run(identity)
    queue = review_queue(store)
    assert len(queue) == 1 and queue[0]["research"]["id"] == research.id
    assert queue[0]["operator_review"] is None and queue[0]["customer_review"] is None
    assert store.get_run(identity) == before
    store.review(identity, research.id, Review(decision="accepted", reason="Labelled customer decision"))
    assert review_queue(store) == []
    store.review(identity, research.id, Review(decision="needs_research", reason="Missing sources"))
    monkeypatch.setattr("shortlist.cli.Settings.load", lambda: settings)
    monkeypatch.setattr("sys.argv", ["shortlist", "review-queue"])
    main()
    output = json.loads(capsys.readouterr().out)
    assert output[0]["customer_review"]["decision"] == "needs_research"
    assert output[0]["operator_review"] is None
    store.delete_run(identity)
    assert review_queue(store) == []
