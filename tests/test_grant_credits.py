import sys
from typing import ClassVar
from uuid import uuid4

import pytest

from shortlist import cli
from shortlist.config import Settings


def hosted(worker_url="postgresql://worker.example/db"):
    return Settings(mode="hosted", app_url="https://app.example", supabase_url="https://auth.example",
                    supabase_publishable_key="sb_publishable_fixture", database_url="postgresql://unused",
                    worker_database_url=worker_url)


def run(monkeypatch, settings, *arguments):
    monkeypatch.setattr(cli.Settings, "load", staticmethod(lambda: settings))
    monkeypatch.setattr(sys, "argv", ["shortlist", "grant-credits", *arguments])
    cli.main()


class FakeWallet:
    grants: ClassVar[list[tuple[int, str, str]]] = []

    def __init__(self, store):
        self.store = store

    def grant(self, quantity, key, description):
        FakeWallet.grants.append((quantity, key, description))

    def balance(self):
        from shortlist.credits import Balance
        return Balance(available=3 + sum(quantity for quantity, _, _ in FakeWallet.grants), reserved=0, used=0)


@pytest.fixture
def wallet(monkeypatch):
    import shortlist.credits
    import shortlist.postgres
    FakeWallet.grants = []
    monkeypatch.setattr(shortlist.credits, "CreditWallet", FakeWallet)
    monkeypatch.setattr(shortlist.postgres, "PostgresStore", lambda dsn, workspace, worker: (dsn, workspace, worker))
    return FakeWallet


def test_plans_grant_labelled_operator_credits_with_a_replay_safe_key(wallet, monkeypatch, capsys):
    workspace = str(uuid4())
    monkeypatch.setenv("SHORTLIST_INTERNAL_WORKSPACES", f"{uuid4()}, {workspace}")
    run(monkeypatch, hosted(), "--workspace", workspace, "--plan", "dev")
    quantity, key, description = wallet.grants[0]
    assert quantity == 500 and key.startswith("operator-dev-500-")
    assert description == "Dev test plan: operator grant, no payment"
    assert '"available": 503' in capsys.readouterr().out
    run(monkeypatch, hosted(), "--workspace", workspace, "--credits", "7", "--key", "pilot-1")
    assert wallet.grants[1] == (7, "pilot-1", "Operator credits: operator grant, no payment")


def test_dev_is_internal_and_refused_for_accounts_outside_the_allowlist(wallet, monkeypatch, capsys):
    monkeypatch.setenv("SHORTLIST_INTERNAL_WORKSPACES", str(uuid4()))
    with pytest.raises(SystemExit):
        run(monkeypatch, hosted(), "--workspace", str(uuid4()), "--plan", "dev")
    assert "dev is internal" in capsys.readouterr().err
    monkeypatch.delenv("SHORTLIST_INTERNAL_WORKSPACES")
    with pytest.raises(SystemExit):
        run(monkeypatch, hosted(), "--workspace", str(uuid4()), "--plan", "dev")
    assert wallet.grants == []


@pytest.mark.parametrize("arguments", [("--plan", "pro", "--credits", "5"), ()])
def test_exactly_one_of_plan_or_credits(wallet, monkeypatch, arguments):
    with pytest.raises(SystemExit):
        run(monkeypatch, hosted(), "--workspace", str(uuid4()), *arguments)
    assert wallet.grants == []


def test_grants_are_hosted_only_and_need_the_worker_credential(wallet, monkeypatch, tmp_path):
    for settings in (Settings(db_path=tmp_path / "local.sqlite3"), hosted(worker_url="")):
        with pytest.raises(SystemExit):
            run(monkeypatch, settings, "--workspace", str(uuid4()), "--plan", "pro")
    assert wallet.grants == []
