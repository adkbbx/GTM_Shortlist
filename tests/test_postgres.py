"""Real PostgreSQL checks. CI supplies its isolated service; local tests use loopback."""
import hashlib
import importlib.util
import os
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from uuid import uuid4

import httpx
import psycopg
import pytest
from fastapi.testclient import TestClient
from psycopg import sql
from psycopg.conninfo import conninfo_to_dict, make_conninfo
from pydantic import SecretStr

from shortlist.api import create_app
from shortlist.auth import verify_user
from shortlist.config import Settings
from shortlist.credits import CreditWallet
from shortlist.domain import Candidate, Criterion, Profile, Review, Source
from shortlist.export import export_run
from shortlist.journal import call_step
from shortlist.postgres import PostgresStore
from shortlist.providers import ProviderError, validate_extraction
from shortlist.store import BudgetExceeded, Conflict
from shortlist.verification import Judgment, Verification
from shortlist.worker import execute_run

pytestmark = pytest.mark.skipif(not os.getenv("SHORTLIST_TEST_PG_URL"), reason="Requires the isolated PostgreSQL service")


@pytest.fixture(scope="module")
def database():
    admin = os.environ["SHORTLIST_TEST_PG_URL"]
    name = "shortlist_test_" + uuid4().hex
    with psycopg.connect(admin, autocommit=True) as db:
        db.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(name)))
    operator = make_conninfo(admin, dbname=name)
    path = Path(__file__).parents[1] / "scripts/migrate_postgres.py"
    spec = importlib.util.spec_from_file_location("shortlist_migration", path)
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)
    migration.migrate(operator)
    migration.migrate(operator)  # Checksummed replay, not duplicate DDL.
    with psycopg.connect(admin, autocommit=True) as db:
        for login, role in (("shortlist_api_test_login", "shortlist_api"),
                            ("shortlist_worker_test_login", "shortlist_worker")):
            if not db.execute("SELECT 1 FROM pg_roles WHERE rolname=%s", (login,)).fetchone():
                db.execute(sql.SQL("CREATE ROLE {} LOGIN NOSUPERUSER NOBYPASSRLS PASSWORD 'isolated-test-only' IN ROLE {}")
                           .format(sql.Identifier(login), sql.Identifier(role)))
    connection = conninfo_to_dict(operator)
    connection.update(user="shortlist_api_test_login", password="isolated-test-only")
    api = SecretStr(make_conninfo(**connection))
    connection["user"] = "shortlist_worker_test_login"
    worker = SecretStr(make_conninfo(**connection))
    yield api, worker, operator
    # The fixture creates this exact uniquely named database; never drop a supplied database.
    with psycopg.connect(admin, autocommit=True) as db:
        db.execute(sql.SQL("DROP DATABASE {} WITH (FORCE)").format(sql.Identifier(name)))


@pytest.fixture
def owners(database):
    api, worker, _ = database
    first, second = uuid4(), uuid4()
    a, b = PostgresStore(api, first), PostgresStore(api, second)
    a.ensure_workspace(); b.ensure_workspace()
    profile = Profile(seller_url="https://seller.example/", offer="Labelled acquisition research service",
                      target="AI business software", criteria=(Criterion(id="ai", description="AI software"),))
    return a, b, worker, profile


def test_isolation_idempotency_and_no_ownerless_access(owners):
    a, b, worker, profile = owners
    first = a.create_run(profile, "same-request-key")
    second = b.create_run(profile, "same-request-key")
    assert first != second
    assert a.create_run(profile, "same-request-key") == first
    assert {r["id"] for r in a.list_runs()} == {first}
    assert {r["id"] for r in b.list_runs()} == {second}
    with pytest.raises(KeyError):
        b.get_run(first)
    assert b.claim(first) is None
    with pytest.raises(ValueError):
        PostgresStore(a.dsn, None)
    observer = PostgresStore(worker, None, worker=True)
    assert first in observer.pending_runs() and second in observer.pending_runs()
    with a.connection() as db:
        assert db.execute("SELECT current_setting('shortlist.workspace_id')").fetchone()[0] == str(a.workspace_id)
    with b.connection() as db:
        assert db.execute("SELECT current_setting('shortlist.workspace_id')").fetchone()[0] == str(b.workspace_id)


def test_cannot_disable_policies_cross_link_records_or_assume_worker(owners):
    a, b, _, profile = owners
    first = a.create_run(profile, "restricted")
    b.create_run(profile, "restricted")
    with pytest.raises(psycopg.errors.InsufficientPrivilege), b.connection() as db:
        db.execute("ALTER TABLE runs DISABLE ROW LEVEL SECURITY")
    with pytest.raises(psycopg.errors.InsufficientPrivilege), b.connection() as db:
        db.execute("SET ROLE shortlist_worker")
    with pytest.raises(psycopg.errors.ForeignKeyViolation), b.connection() as db:
        db.execute("INSERT INTO records(id,run_id,domain,research) VALUES (?,?,?,?)",
                   (uuid4().hex, first, "company.example", "{}"))
    with pytest.raises(psycopg.errors.InsufficientPrivilege), b.connection() as db:
        db.execute("SELECT * FROM search_quotas")


def test_runtime_rejects_operator_credentials(database):
    _, _, operator = database
    store = PostgresStore(SecretStr(operator), uuid4())
    with pytest.raises(ValueError, match="must not bypass"):
        store.ensure_workspace()


def test_concurrent_claim_and_shared_global_allowance_are_atomic(owners):
    a, b, _, profile = owners
    first = a.create_run(profile, "concurrent")
    second = b.create_run(profile, "concurrent")
    with ThreadPoolExecutor(max_workers=6) as pool:
        claims = list(pool.map(lambda _: a.claim(first), range(6)))
    assert sum(f is not None for f in claims) == 1
    fence_a = next(f for f in claims if f is not None)
    fence_b = b.claim(second)
    provider = "labelled-quota-" + uuid4().hex

    def reserve(index):
        owner, identity, fence = (a, first, fence_a) if index % 2 else (b, second, fence_b)
        try:
            return owner.reserve(identity, fence, provider, "search", f"search:{index}", global_cap=3)
        except BudgetExceeded:
            return None

    with ThreadPoolExecutor(max_workers=6) as pool:
        outcomes = list(pool.map(reserve, range(6)))
    assert sum(o is not None for o in outcomes) == 3
    assert sum(len(owner.get_run(identity)["attempts"]) for owner, identity in ((a, first), (b, second))) == 3


def test_real_worker_flow_review_export_cache_and_events_are_isolated(owners):
    a, b, worker, profile = owners
    run_id = a.create_run(profile, "worker-flow")
    scoped = PostgresStore(worker, a.workspace_id, worker=True)
    text = "Labelled fixture: We offer AI business software."
    source = Source(url="https://company.example/", company_domain="company.example", title="Labelled fixture",
                    text=text, content_hash=hashlib.sha256(text.encode()).hexdigest())

    class Search:
        name = "labelled-postgres-fixture"

        def search(self, query, seller_url):
            return [Candidate(domain=source.company_domain, url=source.url, name="Fixture", query=query, provider=self.name)]

    class Model:
        name = "labelled-postgres-fixture"

        def research(self, profile, candidate, sources):
            return validate_extraction({"name": "Fixture", "findings": [{"criterion_id": "ai", "status": "supported",
                "evidence": [{"source_id": source.id, "passage": text, "claim": "AI business software"}]}]},
                profile, candidate.domain, sources)

        def verify(self, profile, record):
            return Verification(judgments=[Judgment(assessment_id="criterion:ai", verdict="entailed",
                                                   reason="Explicit labelled source statement")])

    scoped.worker_heartbeat("labelled-pg-worker")
    assert a.worker_online()
    execute_run(scoped, Settings(), run_id, search=Search(), model=Model(), fetch=lambda *args, **kwargs: source)
    saved = a.get_run(run_id)
    assert saved["status"] == "ready"
    assert saved["credits"] == {"maximum": 3, "used": 1, "reserved": 0, "returned": 2}
    assert saved["records"][0]["credits_used"] == 1
    assert CreditWallet(a).balance().available == 2
    assert len(saved["attempts"]) == 5
    assert saved["events"][-1]["phase"] == "review"
    record = saved["records"][0]["research"]
    with pytest.raises(KeyError):
        b.review(run_id, record["id"], Review(decision="accepted"))
    a.review(run_id, record["id"], Review(decision="accepted", reason="Labelled review"))
    assert "accepted" in export_run(a.get_run(run_id), "json", accepted_only=True)
    assert b.cached_source(source.url, source.company_domain, 24, run_id=uuid4().hex, operation="fetch:company") is None
    with pytest.raises(psycopg.errors.InsufficientPrivilege):
        a.worker_heartbeat("fake-api-worker")
    scoped.remove_worker("labelled-pg-worker")


def test_result_replay_and_stale_fences_preserve_budget(owners):
    a, _, _, profile = owners
    run_id = a.create_run(profile, "replay")
    fence = a.claim(run_id)
    calls = []
    source = Source(url="https://company.example/", company_domain="company.example", title="Fixture",
                    text="Labelled source observation.", content_hash="labelled")

    def dispatch():
        calls.append(True)
        return source

    for _ in range(2):
        value = call_step(a, run_id, fence, 200, kind="fetch", provider="https", operation="fetch:company",
                          inputs={"url": source.url}, function=dispatch, decode=Source.model_validate)
        assert value == source
    assert len(calls) == 1
    assert len(a.get_run(run_id)["attempts"]) == 1
    with a.connection() as db:
        db.execute("UPDATE runs SET lease_until=0 WHERE id=?", (run_id,))
    replacement = a.claim(run_id)
    assert replacement > fence
    with pytest.raises(Conflict):
        a.checkpoint(run_id, fence, "research", {})


def test_free_profile_starts_are_atomic_idempotent_and_not_reset_by_deletion(owners):
    a, _, _, _ = owners

    def start(index):
        try:
            return a.create_draft("https://seller.example/", "demo-" + str(index))
        except BudgetExceeded:
            return None

    with ThreadPoolExecutor(max_workers=6) as pool:
        ids = list(pool.map(start, range(6)))
    assert sum(identity is not None for identity in ids) == 1
    winner = next(index for index, identity in enumerate(ids) if identity)
    assert a.create_draft("https://seller.example/", "demo-" + str(winner)) == ids[winner]
    assert len(a.list_runs()) == 1
    with a.connection() as db:
        db.execute("DELETE FROM runs WHERE id=?", (ids[winner],))
    for index in (2, 3):
        another = a.create_draft("https://seller.example/", "after-deletion-" + str(index))
        with a.connection() as db:
            db.execute("DELETE FROM runs WHERE id=?", (another,))
    with pytest.raises(BudgetExceeded):
        a.create_draft("https://seller.example/", "fourth-profile")
    assert CreditWallet(a).balance().available == 3


def test_hosted_api_verifies_identity_and_scopes_every_route(owners, monkeypatch):
    a, b, worker, _ = owners
    settings = Settings(mode="hosted", database_url=a.dsn, worker_database_url=worker,
                        supabase_url="https://auth.example", supabase_publishable_key="sb_publishable_fixture",
                        app_url="https://app.example")

    def endpoint(request):
        token = request.headers["authorization"]
        if token not in ("Bearer owner-a", "Bearer owner-b"):
            return httpx.Response(401)
        identity = a.workspace_id if token == "Bearer owner-a" else b.workspace_id
        return httpx.Response(200, json={"id": str(identity), "role": "authenticated",
                                        "email_confirmed_at": "2026-10-14T00:00:00Z"})

    monkeypatch.setattr("shortlist.api.verify_user", lambda configuration, token: verify_user(
        configuration, token, transport=httpx.MockTransport(endpoint)))
    client = TestClient(create_app(settings), base_url="https://app.example")
    first_headers = {"Authorization": "Bearer owner-a"}
    second_headers = {"Authorization": "Bearer owner-b"}
    assert client.get("/api/runs").status_code == 401
    assert client.get("/api/runs", headers={"Authorization": "Bearer invalid"}).status_code == 401
    assert client.get("/api/runs", headers={**first_headers, "Host": "attacker.example"}).status_code == 400
    assert client.post("/api/sellers", headers={**first_headers, "Origin": "https://attacker.example"}, json={}).status_code == 403
    body = {"seller_url": "https://seller.example/", "request_key": "same-tenant-key"}
    first = client.post("/api/sellers", headers=first_headers, json=body)
    second = client.post("/api/sellers", headers=second_headers, json=body)
    assert first.status_code == second.status_code == 201
    first_id, second_id = first.json()["id"], second.json()["id"]
    assert first_id != second_id
    assert client.post("/api/sellers", headers=first_headers, json=body).json()["id"] == first_id
    assert client.post("/api/sellers", headers=first_headers, json={**body, "request_key": "another-run"}).status_code == 403
    assert {r["id"] for r in client.get("/api/runs", headers=first_headers).json()} == {first_id}
    for route in (f"/api/runs/{first_id}", f"/api/runs/{first_id}/export"):
        assert client.get(route, headers=second_headers).status_code == 404
    assert client.post(f"/api/runs/{first_id}/confirm", headers=second_headers,
                       json={"offer": "Labelled offer", "target": "AI software",
                             "criteria": [{"id": "ai", "description": "AI software"}]}).status_code == 404
    assert client.post(f"/api/runs/{first_id}/records/invented/review", headers=second_headers,
                       json={"decision": "accepted"}).status_code == 404
    assert client.delete(f"/api/runs/{first_id}", headers=second_headers).status_code == 404
    assert client.delete(f"/api/runs/{first_id}", headers=first_headers).status_code == 409
    scheduler = PostgresStore(worker, None, worker=True)
    scoped = scheduler.for_run(first_id)
    assert scoped.workspace_id == a.workspace_id
    assert scoped.get_run(first_id)["workspace_id"] == a.workspace_id


def test_hosted_worker_loop_selects_workspace_for_each_run(owners, monkeypatch):
    a, b, worker, _ = owners
    first = a.create_draft("https://first.example/", "hosted-worker-a")
    second = b.create_draft("https://second.example/", "hosted-worker-b")
    settings = Settings(mode="hosted", database_url=a.dsn, worker_database_url=worker,
                        supabase_url="https://auth.example", supabase_publishable_key="sb_publishable_fixture",
                        app_url="https://app.example")
    processed = {}

    def execute(store, configuration, run_id):
        # Use actual DB writes through the selected worker's default workspace.
        if run_id in (first, second):
            processed[run_id] = store.workspace_id
            fence = store.claim(run_id)
            store.checkpoint(run_id, fence, "confirmation", {"seller_url": "https://fixture.example/"},
                             status="awaiting_confirmation")

    monkeypatch.setattr("shortlist.worker.execute_run", execute)
    from shortlist.worker import work
    work(settings, once=True)
    assert processed == {first: a.workspace_id, second: b.workspace_id}
    assert a.get_run(first)["status"] == b.get_run(second)["status"] == "awaiting_confirmation"


def test_credit_signup_reserve_delivery_refund_and_replay(owners):
    a, b, worker, profile = owners
    a.ensure_workspace()
    wallet = CreditWallet(a)
    other = CreditWallet(b)
    delivery = CreditWallet(PostgresStore(worker, a.workspace_id, worker=True))
    assert wallet.balance().model_dump() == {"available": 3, "reserved": 0, "used": 0}
    run_id = a.create_run(profile, "wallet-demo")
    wallet.reserve(run_id, 3)
    wallet.reserve(run_id, 3)
    assert wallet.balance().model_dump() == {"available": 0, "reserved": 3, "used": 0}
    with pytest.raises(Conflict):
        wallet.reserve(run_id, 2)
    with pytest.raises(KeyError):
        other.reserve(run_id, 1)
    delivery.consume(run_id, "company.example")
    delivery.consume(run_id, "company.example")
    assert wallet.balance().model_dump() == {"available": 0, "reserved": 2, "used": 1}
    delivery.settle(run_id)
    delivery.settle(run_id)
    assert wallet.balance().model_dump() == {"available": 2, "reserved": 0, "used": 1}
    with pytest.raises(Conflict):
        delivery.consume(run_id, "late-company.example")
    assert other.balance().available == 3


def test_credit_concurrent_reservations_cannot_overspend(owners):
    a, _, worker, profile = owners
    first = a.create_draft(profile.seller_url, "credit-first")
    scoped = PostgresStore(worker, a.workspace_id, worker=True)
    # Construct a second labelled run with the worker, without resetting the legacy demo.
    second = uuid4().hex
    with scoped.connection() as db:
        db.execute("INSERT INTO runs(id,request_key,payload_hash,profile,status,stage,created_at,updated_at) "
                   "SELECT ?,?,payload_hash,profile,status,stage,created_at,updated_at FROM runs WHERE id=?",
                   (second, "credit-second", first))
    wallet = CreditWallet(a)
    assert wallet.balance().available == 3
    assert wallet.balance().reserved == 0

    def reserve(identity):
        try:
            wallet.reserve(identity, 3)
            return identity
        except BudgetExceeded:
            return None

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(reserve, (first, second)))
    assert sum(result is not None for result in results) == 1
    assert wallet.balance().available == 0
    charged = CreditWallet(scoped)
    with ThreadPoolExecutor(max_workers=6) as pool:
        list(pool.map(lambda _: charged.consume(next(result for result in results if result), "same.example"), range(6)))
    assert wallet.balance().used == 1


def test_credit_grants_replay_once_and_ledger_cannot_be_changed(owners):
    a, b, worker, _ = owners
    wallet = CreditWallet(a)
    delivery = CreditWallet(PostgresStore(worker, a.workspace_id, worker=True))
    with pytest.raises(ValueError):
        wallet.grant(20, "unverified-purchase", "Never a client grant")
    delivery.grant(20, "labelled-purchase", "Labelled operator grant, not a real payment")
    delivery.grant(20, "labelled-purchase", "Labelled operator grant, not a real payment")
    assert wallet.balance().available == 23
    with pytest.raises(Conflict):
        delivery.grant(100, "labelled-purchase", "Changed quantity")
    with pytest.raises(psycopg.errors.InsufficientPrivilege), delivery.store.connection() as db:
        db.execute("UPDATE credit_entries SET amount=100 WHERE operation_key='signup'")
    with pytest.raises(psycopg.errors.InsufficientPrivilege), a.connection() as db:
        db.execute("INSERT INTO credit_entries(workspace_id,operation_key,kind,amount,description) VALUES (?,'fake','purchase',100,'fake')",
                   (a.workspace_id,))
    with b.connection() as db:
        assert db.execute("SELECT count(*) FROM credit_entries WHERE workspace_id=?", (a.workspace_id,)).fetchone()[0] == 0


def test_credit_failed_batch_releases_all_and_debit_rollback_is_atomic(owners):
    a, _, worker, profile = owners
    run_id = a.create_run(profile, "credit-rollback")
    wallet = CreditWallet(a)
    delivery = CreditWallet(PostgresStore(worker, a.workspace_id, worker=True))
    wallet.reserve(run_id, 3)
    with pytest.raises(RuntimeError, match="Labelled crash"), delivery.store.connection() as db:
        delivery.store.begin(db)
        delivery.consume_in_transaction(db, run_id, "rollback.example")
        raise RuntimeError("Labelled crash before transaction commit")
    assert wallet.balance().model_dump() == {"available": 0, "reserved": 3, "used": 0}
    delivery.settle(run_id)
    assert wallet.balance().model_dump() == {"available": 3, "reserved": 0, "used": 0}


@pytest.mark.parametrize("committed", [False, True])
def test_actual_process_death_never_duplicates_credit_debits(owners, committed):
    a, _, worker, profile = owners
    run_id = a.create_run(profile, "credit-process-death")
    wallet = CreditWallet(a)
    wallet.reserve(run_id, 3)
    script = """
import os
from uuid import UUID
from pydantic import SecretStr
from shortlist.postgres import PostgresStore
from shortlist.credits import CreditWallet
store=PostgresStore(SecretStr(os.environ['CREDIT_TEST_DSN']),UUID(os.environ['CREDIT_TEST_OWNER']),worker=True)
wallet=CreditWallet(store)
if os.environ['CREDIT_TEST_COMMITTED']=='yes':
    wallet.consume(os.environ['CREDIT_TEST_RUN'],'crash.example')
    os._exit(23)
with store.connection() as db:
    store.begin(db)
    wallet.consume_in_transaction(db,os.environ['CREDIT_TEST_RUN'],'crash.example')
    os._exit(23)
"""
    child = subprocess.run([sys.executable, "-c", script], check=False, capture_output=True, timeout=15,
                           env={**os.environ, "CREDIT_TEST_DSN": worker.get_secret_value(),
                                "CREDIT_TEST_OWNER": str(a.workspace_id), "CREDIT_TEST_RUN": run_id,
                                "CREDIT_TEST_COMMITTED": "yes" if committed else "no"})
    assert child.returncode == 23
    assert wallet.balance().used == int(committed)
    CreditWallet(PostgresStore(worker, a.workspace_id, worker=True)).consume(run_id, "crash.example")
    assert wallet.balance().used == 1


def test_credit_migration_preserves_already_used_legacy_demo(database):
    _, _, operator = database
    name = "shortlist_credit_migration_" + uuid4().hex
    admin = make_conninfo(operator, dbname="postgres")
    fresh, used = uuid4(), uuid4()
    with psycopg.connect(admin, autocommit=True) as db:
        db.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(name)))
    try:
        with psycopg.connect(make_conninfo(operator, dbname=name)) as db:
            folder = Path(__file__).parents[1] / "migrations"
            for filename in ("001_hosted.sql", "002_demo.sql"):
                db.execute((folder / filename).read_text(encoding="utf-8"))
            db.execute("INSERT INTO shortlist.workspaces(id,demo_run_id) VALUES (%s,NULL),(%s,'legacy-run')", (fresh, used))
            db.execute("INSERT INTO shortlist.runs(id,workspace_id,request_key,payload_hash,profile,status,stage,created_at,updated_at) "
                       "VALUES ('legacy-run',%s,'legacy','fixture','{}','awaiting_confirmation','confirmation','fixture','fixture')", (used,))
            db.execute((folder / "003_credit_wallet.sql").read_text(encoding="utf-8"))
            grants = dict(db.execute("SELECT workspace_id,amount FROM shortlist.credit_entries").fetchall())
            assert grants == {fresh: 3, used: 0}
            assert db.execute("SELECT demo_run_id FROM shortlist.workspaces WHERE id=%s", (used,)).fetchone()[0] == "legacy-run"
            db.execute((folder / "004_credit_delivery.sql").read_text(encoding="utf-8"))
            assert db.execute("SELECT legacy_credit_exempt FROM shortlist.runs WHERE id='legacy-run'").fetchone()[0] is True
    finally:
        with psycopg.connect(admin, autocommit=True) as db:
            db.execute(sql.SQL("DROP DATABASE {} WITH (FORCE)").format(sql.Identifier(name)))


@pytest.mark.parametrize("outcome,expected", [("extraction-failure", 0), ("verification-failure", 0),
                                            ("unknown", 1), ("non-fit", 1), ("mixed", 1)])
def test_worker_bills_completed_research_and_returns_technical_failures(owners, outcome, expected):
    a, _, worker, profile = owners
    run_id = a.create_run(profile, "delivery-policy")
    scoped = PostgresStore(worker, a.workspace_id, worker=True)
    text = "We do not offer AI software." if outcome == "non-fit" else "We offer AI software for businesses."
    snapshots = {}

    def fetch(url, expected_domain=None):
        source = Source(url=url, company_domain=expected_domain, title="Labelled credit fixture", text=text,
                        content_hash=hashlib.sha256(text.encode()).hexdigest())
        snapshots[expected_domain] = source
        return source

    class Search:
        name = "labelled-credit-search"

        def search(self, query, seller_url):
            domains = ("first.example", "second.example") if outcome == "mixed" else ("first.example",)
            return [Candidate(domain=domain, url="https://" + domain + "/", name="Fixture", query=query, provider=self.name)
                    for domain in domains]

    class Model:
        name = "labelled-credit-model"

        def research(self, profile, candidate, sources):
            if outcome == "extraction-failure":
                raise ProviderError("Labelled model failure")
            finding = {"criterion_id": "ai", "status": "unknown", "reason": "Evidence does not establish the criterion"}
            if outcome != "unknown":
                finding = {"criterion_id": "ai", "status": "contradicted" if outcome == "non-fit" else "supported",
                           "evidence": [{"source_id": sources[0].id, "passage": text, "claim": text}]}
            return validate_extraction({"name": "Fixture", "findings": [finding]}, profile, candidate.domain, sources)

        def verify(self, profile, record):
            if outcome == "verification-failure" or (outcome == "mixed" and record.domain == "second.example"):
                raise ProviderError("Labelled verifier outage")
            return Verification(judgments=[Judgment(assessment_id="criterion:ai", verdict="entailed", reason="Explicit fixture")])

    execute_run(scoped, Settings(), run_id, search=Search(), model=Model(), fetch=fetch)
    saved = a.get_run(run_id)
    assert saved["credits"] == {"maximum": 3, "used": expected, "reserved": 0, "returned": 3 - expected}
    assert CreditWallet(a).balance().available == 3 - expected
    assert sum(record["credits_used"] for record in saved["records"]) == expected
    if outcome == "non-fit":
        assert saved["records"][0]["research"]["qualification"] == "does_not_fit", saved["records"][0]["research"]
    if outcome == "unknown":
        assert saved["records"][0]["research"]["findings"][0]["status"] == "unknown"


def test_confirmation_reserves_selected_size_and_rejects_changed_size(owners):
    a, _, worker, profile = owners
    run_id = a.create_draft(profile.seller_url, "one-company")
    scoped = PostgresStore(worker, a.workspace_id, worker=True)
    scoped.checkpoint(run_id, scoped.claim(run_id), "confirmation", {"seller_url": profile.seller_url}, "awaiting_confirmation")
    a.confirm_draft(run_id, profile, 1)
    a.confirm_draft(run_id, profile, 1)
    with pytest.raises(Conflict):
        a.confirm_draft(run_id, profile, 2)
    assert a.get_run(run_id)["checkpoint"]["company_limit"] == 1
    assert CreditWallet(a).balance().model_dump() == {"available": 2, "reserved": 1, "used": 0}


def test_assigned_worker_cannot_reuse_other_workspace_cache_or_read_run(owners):
    a, b, worker, profile = owners
    run_id = a.create_run(profile, "worker-cache-scope")
    scoped_a = PostgresStore(worker, a.workspace_id, worker=True)
    scoped_b = PostgresStore(worker, b.workspace_id, worker=True)
    source = Source(url="https://shared.example/", company_domain="shared.example", title="Owner A fixture",
                    text="Owner A preserved observation", content_hash="labelled")
    scoped_a.cache_source(run_id, scoped_a.claim(run_id), source.url, source)
    assert scoped_a.cached_source(source.url, source.company_domain, 24, run_id=run_id, operation="fetch:new") == source
    assert scoped_b.cached_source(source.url, source.company_domain, 24, run_id=uuid4().hex, operation="fetch:new") is None
    with pytest.raises(KeyError):
        scoped_b.get_run(run_id)
    assert PostgresStore(worker, None, worker=True).get_run(run_id)["id"] == run_id


@pytest.mark.parametrize("committed", [False, True])
def test_actual_process_death_keeps_company_record_and_credit_debit_atomic(owners, committed):
    a, _, worker, profile = owners
    run_id = a.create_run(profile, "record-credit-crash")
    scoped = PostgresStore(worker, a.workspace_id, worker=True)
    fence = scoped.claim(run_id)
    text = "We offer AI software for business teams."
    source = Source(url="https://atomic.example/", company_domain="atomic.example", title="Labelled atomic fixture",
                    text=text, content_hash=hashlib.sha256(text.encode()).hexdigest())
    record = validate_extraction({"name": "Atomic fixture", "findings": [{"criterion_id": "ai", "status": "supported",
                                  "evidence": [{"source_id": source.id, "passage": text, "claim": text}]}]},
                                 profile, source.company_domain, (source,))
    script = """
import os
from uuid import UUID
from pydantic import SecretStr
from shortlist.postgres import PostgresStore
from shortlist.domain import Research
class CrashStore(PostgresStore):
    def delivered(self,db,run_id,record,billable):
        super().delivered(db,run_id,record,billable)
        if os.environ['CREDIT_TEST_COMMITTED']=='no': os._exit(23)
store=CrashStore(SecretStr(os.environ['CREDIT_TEST_DSN']),UUID(os.environ['CREDIT_TEST_OWNER']),worker=True)
store.save_record(os.environ['CREDIT_TEST_RUN'],int(os.environ['CREDIT_TEST_FENCE']),Research.model_validate_json(os.environ['CREDIT_TEST_RECORD']))
os._exit(23)
"""
    result = subprocess.run([sys.executable, "-c", script], check=False, capture_output=True, timeout=15,
                            env={**os.environ, "CREDIT_TEST_DSN": worker.get_secret_value(),
                                 "CREDIT_TEST_OWNER": str(a.workspace_id), "CREDIT_TEST_RUN": run_id,
                                 "CREDIT_TEST_FENCE": str(fence), "CREDIT_TEST_RECORD": record.model_dump_json(),
                                 "CREDIT_TEST_COMMITTED": "yes" if committed else "no"})
    assert result.returncode == 23
    assert len(a.get_run(run_id)["records"]) == int(committed)
    assert CreditWallet(a).balance().used == int(committed)
    with scoped.connection() as db:
        db.execute("UPDATE runs SET lease_until=0 WHERE id=?", (run_id,))
    scoped.save_record(run_id, scoped.claim(run_id), record)
    assert len(a.get_run(run_id)["records"]) == CreditWallet(a).balance().used == 1


def test_research_deletion_preserves_wallet_and_other_workspace_cache(owners):
    a, b, worker, profile = owners
    identity = a.create_run(profile, "delete-research")
    scoped = PostgresStore(worker, a.workspace_id, worker=True)
    fence = scoped.claim(identity)
    text = "We offer AI software for business teams."
    source = Source(url="https://delete.example/", company_domain="delete.example", title="Labelled deletion fixture",
                    text=text, content_hash=hashlib.sha256(text.encode()).hexdigest())
    scoped.cache_source(identity, fence, source.url, source)
    record = validate_extraction({"name": "Deletion fixture", "findings": [{"criterion_id": "ai", "status": "supported",
                                  "evidence": [{"source_id": source.id, "passage": text, "claim": text}]}]},
                                 profile, source.company_domain, (source,))
    scoped.save_record(identity, fence, record)
    scoped.checkpoint(identity, fence, "complete", {}, "ready")
    other = b.create_run(profile, "unrelated-research")
    scoped_b = PostgresStore(worker, b.workspace_id, worker=True)
    other_source = source.model_copy(update={"id": uuid4().hex})
    scoped_b.cache_source(other, scoped_b.claim(other), source.url, other_source)
    before = CreditWallet(a).balance()
    with pytest.raises(KeyError):
        b.delete_run(identity)
    a.delete_run(identity)
    a.delete_run(identity)
    assert CreditWallet(a).balance() == before
    assert before.available == 2 and before.used == 1
    assert a.list_runs() == []
    with pytest.raises(KeyError):
        a.get_run(identity)
    with pytest.raises(Conflict):
        a.create_run(profile, "delete-research")
    assert scoped_b.cached_source(source.url, source.company_domain, 24, run_id=other, operation="fetch:new") == other_source
    with a.connection() as db:
        assert db.execute("SELECT count(*) FROM records WHERE run_id=?", (identity,)).fetchone()[0] == 0
        assert db.execute("SELECT count(*) FROM source_cache").fetchone()[0] == 0
        assert db.execute("SELECT count(*) FROM credit_entries").fetchone()[0] == 2
