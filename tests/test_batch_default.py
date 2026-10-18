"""New runs research one company unless the user asks for more."""
import inspect

from shortlist.api import Confirmation
from shortlist.domain import Criterion, Profile
from shortlist.store import Store


def test_new_confirmations_default_to_one_company():
    assert Confirmation.model_fields["company_limit"].default == 1
    assert inspect.signature(Store.confirm_draft).parameters["company_limit"].default == 1


def test_confirming_without_a_limit_saves_one(tmp_path):
    store = Store(tmp_path / "batch.sqlite3")
    profile = Profile(seller_url="https://seller.example/", offer="Labelled fixture offer for software teams",
                      target="Labelled fixture software companies", criteria=(Criterion(id="a", description="Sells software"),))
    run_id = store.create_draft("https://seller.example/", "batch-default")
    store.checkpoint(run_id, store.claim(run_id), "confirmation", {"seller_url": "https://seller.example/"},
                     "awaiting_confirmation")
    store.confirm_draft(run_id, profile)
    assert store.get_run(run_id)["checkpoint"]["company_limit"] == 1
