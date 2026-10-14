"""Real PostgreSQL checks. CI supplies its isolated service; local tests use loopback."""
import hashlib
import importlib.util
import os
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from uuid import uuid4

import psycopg
import pytest
from psycopg import sql
from psycopg.conninfo import conninfo_to_dict, make_conninfo
from pydantic import SecretStr

from shortlist.config import Settings
from shortlist.domain import Candidate, Criterion, Profile, Review, Source
from shortlist.export import export_run
from shortlist.journal import call_step
from shortlist.postgres import PostgresStore
from shortlist.providers import validate_extraction
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
