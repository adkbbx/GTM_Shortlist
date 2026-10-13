from concurrent.futures import ThreadPoolExecutor

import pytest

from shortlist.domain import Criterion, Profile
from shortlist.store import BudgetExceeded, Conflict, Store


@pytest.fixture
def setup(tmp_path):
    store = Store(tmp_path / "test.sqlite3")
    profile = Profile(seller_url="https://eygentic.com", offer="Acquisition research and experiments",
                      target="AI software startups", criteria=(Criterion(id="ai", description="AI software"),))
    run = store.create_run(profile, "same-key")
    return store, profile, run


def test_idempotent_command(setup):
    store, profile, run = setup
    duplicate = Profile(**profile.model_dump(exclude={"id", "confirmed_at"}))
    assert store.create_run(duplicate, "same-key") == run
    with pytest.raises(Conflict):
        store.create_run(profile.model_copy(update={"target": "Different seller target"}), "same-key")


def test_restart_and_fencing(setup):
    store, _, run = setup
    fence = store.claim(run, lease_seconds=0)
    restarted = Store(store.path)
    new_fence = restarted.claim(run)
    with pytest.raises(Conflict):
        store.checkpoint(run, fence, "research", {})
    restarted.checkpoint(run, new_fence, "research", {"completed": ["example.com"]})
    assert Store(store.path).get_run(run)["checkpoint"]["completed"] == ["example.com"]


def test_atomic_attempt_cap(setup):
    store, _, run = setup
    fence = store.claim(run)
    def reserve(i):
        try:
            store.reserve(run, fence, "tavily", "search", f"search-{i}")
            return True
        except BudgetExceeded:
            return False
    with ThreadPoolExecutor(max_workers=8) as pool:
        assert sum(pool.map(reserve, range(12))) == 4
    assert len(store.get_run(run)["attempts"]) == 4


def test_global_cap_and_uncertain_outcome_count(setup):
    store, profile, run = setup
    fence = store.claim(run)
    store.reserve(run, fence, "serpapi", "search", "one", global_cap=1)
    other = store.create_run(profile, "other")
    with pytest.raises(BudgetExceeded):
        store.reserve(other, store.claim(other), "serpapi", "search", "two", global_cap=1)
    with pytest.raises(Conflict):
        store.reserve(run, fence, "serpapi", "search", "one")
