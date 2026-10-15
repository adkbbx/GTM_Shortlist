"""Offline proof of the opt-in evaluation runner. All provider work is synthetic."""
import hashlib
import os

import pytest

from scripts import evaluate_shortlist
from scripts.ui_test_providers import FixtureModel, FixtureSearch, fixture_fetch
from shortlist.domain import Profile
from shortlist.store import Conflict, Store
from shortlist.worker import execute_run


def test_confirmed_target_evaluation_is_read_only_bounded_and_replayable(tmp_path, monkeypatch):
    source = tmp_path / "source.sqlite3"
    store = Store(source)
    draft = FixtureModel().seller(None)
    profile = Profile(seller_url="https://seller.example/", offer=draft.offer,
                      target=draft.target, criteria=tuple(draft.criteria))
    original = store.create_run(profile, "labelled-source")
    before = hashlib.sha256(source.read_bytes()).hexdigest()
    output = tmp_path / "output.sqlite3"
    provider = tmp_path / "labelled.env"
    provider.write_text("SHORTLIST_SEARCH_PROVIDER=serpapi\n", encoding="utf-8")
    args = ["--source-db", str(source), "--source-run", original, "--output-db", str(output),
            "--provider-env", str(provider), "--allow-provider-calls"]
    invoked = []

    def offline(store, settings, identity):
        invoked.append(settings.global_search_cap)
        return execute_run(store, settings, identity, search=FixtureSearch(), model=FixtureModel(), fetch=fixture_fetch)
    monkeypatch.setattr(evaluate_shortlist, "execute_run", offline)
    evaluate_shortlist.main(args)
    result = Store(output).get_run(Store(output).list_runs()[0]["id"])
    assert len(result["records"]) == 2
    assert result["checkpoint"]["selection_policy"] == 3
    assert result["checkpoint"]["evaluation"]["source_run"] == original
    assert result["profile"] == profile.model_dump(mode="json")
    assert sum(a["kind"] == "search" for a in result["attempts"]) == 2
    assert sum(a["kind"] == "model" for a in result["attempts"]) == 4
    evaluate_shortlist.main(args)
    replay = Store(output).get_run(result["id"])
    assert replay["attempts"] == result["attempts"]
    assert replay["records"] == result["records"]
    assert invoked == [2, 2]
    assert hashlib.sha256(source.read_bytes()).hexdigest() == before
    fence = store.claim(original)
    store.checkpoint(original, fence, "discovery", {"discovery_terms": "Changed context"}, "queued")
    with pytest.raises(Conflict, match="another saved target context"):
        evaluate_shortlist.main(args)
    assert invoked == [2, 2]


@pytest.mark.parametrize("alias", [False, True])
def test_evaluation_rejects_source_alias_before_reading_credentials(tmp_path, monkeypatch, alias):
    source = tmp_path / "source.sqlite3"
    source.write_bytes(b"Untouched labelled source")
    output = tmp_path / "alias.sqlite3" if alias else source
    if alias:
        os.link(source, output)

    def forbidden(*args):
        raise AssertionError("Credentials must not be read")
    monkeypatch.setattr(evaluate_shortlist, "dotenv_values", forbidden)
    with pytest.raises(ValueError, match="must be different"):
        evaluate_shortlist.main(["--source-db", str(source), "--source-run", "fixture",
                                "--output-db", str(output), "--allow-provider-calls"])
    assert source.read_bytes() == b"Untouched labelled source"
