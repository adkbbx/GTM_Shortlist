from concurrent.futures import ThreadPoolExecutor
from threading import Event

from fastapi.testclient import TestClient

from scripts.landing_demo_preview import create_preview_app
from shortlist.api import create_app
from shortlist.config import Settings
from shortlist.local_service import LocalResearchService
from shortlist.store import Store


def ready_settings(tmp_path):
    return Settings(db_path=tmp_path / "research.sqlite3", tavily_key="labelled-fixture-search",
                    gemma_base_url="https://labelled-fixture.example/v1", gemma_model="fixture")


def test_start_is_explicit_idempotent_and_shutdown_removes_heartbeat(tmp_path):
    settings = ready_settings(tmp_path)
    store = Store(settings.db_path)
    service = LocalResearchService(settings)
    assert not store.worker_online()
    try:
        with ThreadPoolExecutor(max_workers=4) as pool:
            list(pool.map(lambda _: service.start(), range(4)))
        assert service.thread.is_alive()
        assert store.worker_online()
        with store.connection() as db:
            assert db.execute("SELECT count(*) FROM worker_heartbeats").fetchone()[0] == 1
    finally:
        service.close()
    assert not service.thread.is_alive()
    assert not store.worker_online()


def test_api_starts_real_worker_and_processes_only_labelled_synthetic_sources(tmp_path, monkeypatch):
    from scripts.ui_test_providers import FixtureModel, FixtureSearch, fixture_fetch
    from shortlist.worker import execute_run
    settings = ready_settings(tmp_path)
    store = Store(settings.db_path)
    identity = store.create_draft("https://seller-fixture.example/", "service-synthetic-job")
    completed = Event()
    def synthetic(scoped, configuration, run_id):
        execute_run(scoped, configuration, run_id, search=FixtureSearch(), model=FixtureModel(), fetch=fixture_fetch)
        completed.set()
    monkeypatch.setattr("shortlist.worker.execute_run", synthetic)
    with TestClient(create_app(settings), base_url="http://127.0.0.1:8014") as client:
        assert client.get("/api/health").json()["worker_online"] is False
        response = client.post("/api/local/service/start", headers={"Origin": "http://127.0.0.1:8014"},
                               json={"confirmation": "start_research_service"})
        assert response.status_code == 200
        assert response.json()["worker_online"] is True
        assert completed.wait(5)
        assert store.get_run(identity)["status"] != "queued"
        assert client.post("/api/local/service/start", headers={"Origin": "http://127.0.0.1:8014"},
                           json={"confirmation": "start_research_service"}).status_code == 200
    assert not store.worker_online()


def test_start_rejects_missing_setup_untrusted_requests_hosted_and_preview(tmp_path):
    settings = Settings(db_path=tmp_path / "missing.sqlite3")
    command = {"confirmation": "start_research_service"}
    path = "/api/local/service/start"
    headers = {"Origin": "http://127.0.0.1:8014"}
    with TestClient(create_app(settings), base_url="http://127.0.0.1:8014") as client:
        assert client.post(path, headers=headers, json=command).status_code == 409
        assert client.post(path, json=command).status_code == 403
        assert client.post(path, headers={"Origin": "https://attacker.example"}, json=command).status_code == 403
        assert client.post(path, headers=headers, json={}).status_code == 422
        assert client.post(path, headers=headers, json={**command, "extra": "labelled-secret"}).status_code == 422
        assert client.post(path, headers=headers, json={"confirmation": "x" * 3000}).status_code == 413
        assert not client.get("/api/health").json()["worker_online"]
    preview = TestClient(create_preview_app(tmp_path / "preview.sqlite3"))
    assert preview.post(path, json=command).status_code == 409
    hosted = settings.model_copy(update={"mode": "hosted", "app_url": "https://app.example"})
    assert TestClient(create_app(hosted), base_url="https://app.example").post(path, json=command).status_code == 404


def test_failed_start_is_retryable_without_exposing_internal_exception(tmp_path, monkeypatch):
    from shortlist.worker import work
    settings = ready_settings(tmp_path)
    def fail(*args, **kwargs):
        raise RuntimeError("labelled-secret-must-not-be-returned")
    monkeypatch.setattr("shortlist.worker.work", fail)
    with TestClient(create_app(settings), base_url="http://127.0.0.1:8014") as client:
        kwargs = {"headers": {"Origin": "http://127.0.0.1:8014"}, "json": {"confirmation": "start_research_service"}}
        response = client.post("/api/local/service/start", **kwargs)
        assert response.status_code == 409
        assert "labelled-secret" not in response.text
        monkeypatch.setattr("shortlist.worker.work", work)
        assert client.post("/api/local/service/start", **kwargs).status_code == 200


def test_worker_stop_event_prevents_claiming_another_queued_job(tmp_path, monkeypatch):
    from shortlist.worker import work
    settings = ready_settings(tmp_path)
    store = Store(settings.db_path)
    store.create_draft("https://first.example/", "first-stopping-fixture")
    store.create_draft("https://second.example/", "second-stopping-fixture")
    stopped = Event()
    received = []
    def execute(scoped, configuration, run_id):
        received.append(run_id)
        stopped.set()
    monkeypatch.setattr("shortlist.worker.execute_run", execute)
    work(settings, stopped=stopped)
    assert len(received) == 1
    assert not store.worker_online()


def test_existing_supervised_worker_is_reused_and_not_owned_by_api(tmp_path):
    settings = ready_settings(tmp_path)
    store = Store(settings.db_path)
    store.worker_heartbeat("labelled-external-worker")
    service = LocalResearchService(settings)
    service.start()
    assert service.thread is None
    service.close()
    assert store.worker_online()
    store.remove_worker("labelled-external-worker")


def test_open_when_ready_waits_for_the_api_before_opening_the_browser():
    from shortlist.local_server import open_when_ready
    answers, opened = iter([OSError(), False, True]), []
    def probe():
        answer = next(answers)
        if isinstance(answer, Exception):
            raise answer
        return answer
    assert open_when_ready('http://127.0.0.1:8014/', opener=opened.append, probe=probe, wait=lambda: None)
    assert opened == ['http://127.0.0.1:8014/']


def test_open_when_ready_gives_up_quietly_when_the_api_never_answers():
    from shortlist.local_server import open_when_ready
    opened = []
    assert not open_when_ready('http://127.0.0.1:8014/', attempts=3, opener=opened.append, probe=lambda: False, wait=lambda: None)
    assert opened == []
