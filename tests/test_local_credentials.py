import os
import sqlite3
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor

import pytest
from fastapi.testclient import TestClient
from pydantic import SecretStr

from shortlist.api import create_app
from shortlist.config import Settings
from shortlist.local_credentials import (
    CredentialUnavailable,
    LocalCredentials,
    apply_local_credentials,
    validate_tavily_key,
)


def test_actual_private_storage_roundtrip_and_separate_process(tmp_path):
    credentials = LocalCredentials(tmp_path / "research.sqlite3")
    assert credentials.read() is None
    key = SecretStr("tvly-labelled-fixture-not-real")
    credentials.save(key)
    assert credentials.read() == key
    raw = credentials.path.read_bytes()
    if os.name == "nt":
        assert key.get_secret_value().encode() not in raw
        assert b"SHORTLIST-DPAPI1\n" in raw
    else:
        assert credentials.path.stat().st_mode & 0o077 == 0
    result = subprocess.run([sys.executable, "-c", ("import sys; from pathlib import Path; "
                             "from shortlist.local_credentials import LocalCredentials; "
                             "assert LocalCredentials(Path(sys.argv[1])).read().get_secret_value() == 'tvly-labelled-fixture-not-real'; "
                             "print('private read verified')"), str(tmp_path / "research.sqlite3")],
                            check=False, capture_output=True, text=True, timeout=10)
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "private read verified"


def test_concurrent_replacement_is_complete_and_failed_write_keeps_old_key(tmp_path, monkeypatch):
    credentials = LocalCredentials(tmp_path / "research.sqlite3")
    first, second = SecretStr("tvly-labelled-fixture-first"), SecretStr("tvly-labelled-fixture-second")
    credentials.save(first)
    def replace(index):
        credentials.save(first if index % 2 else second)
        assert credentials.read() in (first, second)
    with ThreadPoolExecutor(max_workers=4) as pool:
        list(pool.map(replace, range(12)))
    previous = credentials.read()
    connect = sqlite3.connect
    class FailedCommit(sqlite3.Connection):
        def commit(self):
            raise sqlite3.OperationalError("Labelled commit failure")
    monkeypatch.setattr(sqlite3, "connect", lambda *args, **kwargs: connect(*args, **kwargs, factory=FailedCommit))
    with pytest.raises(CredentialUnavailable):
        credentials.save(second)
    assert credentials.read() == previous


@pytest.mark.parametrize("key", ["", "wrong-key", "tvly-short", "tvly-" + "x" * 252, "tvly-linebreak\nfixture", "tvly-🚫fixture"])
def test_validation_never_echoes_key(key):
    with pytest.raises(ValueError) as raised:
        validate_tavily_key(key)
    assert str(raised.value) == "Enter a valid tvly-prefixed Tavily API key"


def test_corruption_fails_closed_and_dynamic_settings_never_mutate_original(tmp_path):
    settings = Settings(db_path=tmp_path / "research.sqlite3", search_provider="serpapi")
    credentials = LocalCredentials(settings.db_path)
    credentials.save(SecretStr("tvly-labelled-dynamic-fixture"))
    assert apply_local_credentials(settings).search_provider == "tavily"
    assert apply_local_credentials(settings).readiness()["search"] is True
    assert settings.search_provider == "serpapi"
    credentials.path.write_bytes(b"broken private config")
    with pytest.raises(CredentialUnavailable):
        credentials.read()
    hosted = settings.model_copy(update={"mode": "hosted"})
    assert apply_local_credentials(hosted) is hosted


@pytest.mark.skipif(os.name == "nt", reason="POSIX mode boundary; Windows uses actual DPAPI above")
def test_posix_broad_permissions_are_rejected(tmp_path):
    credentials = LocalCredentials(tmp_path / "research.sqlite3")
    credentials.save(SecretStr("tvly-labelled-permissions-fixture"))
    credentials.path.chmod(0o644)
    with pytest.raises(CredentialUnavailable):
        credentials.read()


def test_local_key_boundary_never_echoes_or_overwrites_on_rejection(tmp_path):
    settings = Settings(db_path=tmp_path / "research.sqlite3")
    client = TestClient(create_app(settings), base_url="http://127.0.0.1:8014")
    route = "/api/local/tavily"
    headers = {"Origin": "http://127.0.0.1:8014"}
    key = "tvly-labelled-fixture-api-secret"
    assert client.get("/api/health").json()["search_ready"] is False
    saved = client.post(route, headers=headers, json={"key": key})
    assert saved.status_code == 200
    assert saved.json()["search_ready"] is True
    assert key not in saved.text
    assert key not in client.get("/api/health").text
    assert key not in client.get("/openapi.json").text
    assert key not in client.get("/api/runs").text
    for response, status in (
        (client.post(route, json={"key": key}), 403),
        (client.post(route, headers={"Origin": "https://attacker.example"}, json={"key": key}), 403),
        (client.post(route, headers={"Host": "attacker.example"}, json={"key": key}), 400),
        (client.post(route, headers=headers, content=key), 415),
        (client.post(route, headers=headers, json={"key": key, "extra": key}), 422),
        (client.post(route, headers=headers, json={"key": key + "\n"}), 422),
        (client.post(route, headers={**headers, "Content-Type": "application/json"}, content=b'{"key":'), 422),
        (client.post(route, headers=headers, json={"key": key * 100}), 413),
    ):
        assert response.status_code == status
        assert key not in response.text
        assert LocalCredentials(settings.db_path).read().get_secret_value() == key
    schema = client.get("/openapi.json").json()["paths"][route]["post"]["requestBody"]
    assert schema["content"]["application/json"]["schema"]["properties"]["key"]["writeOnly"] is True


def test_hosted_provider_setup_is_unavailable_without_touching_private_file(tmp_path):
    settings = Settings(mode="hosted", db_path=tmp_path / "research.sqlite3", database_url=SecretStr("labelled-unused"),
                        supabase_url="https://auth.example", supabase_publishable_key="sb_publishable_fixture",
                        app_url="https://app.example")
    client = TestClient(create_app(settings), base_url="https://app.example")
    result = client.post("/api/local/tavily", headers={"Origin": "https://app.example"}, json={"key": "tvly-labelled-fixture"})
    assert result.status_code == 404
    assert not LocalCredentials(settings.db_path).path.exists()


def test_next_worker_run_loads_new_key_without_restarting_original_settings(tmp_path, monkeypatch):
    from shortlist.domain import Criterion, Profile
    from shortlist.store import Store
    from shortlist.worker import work
    settings = Settings(db_path=tmp_path / "research.sqlite3")
    store = Store(settings.db_path)
    identity = store.create_run(Profile(seller_url="https://seller.example/", offer="Labelled seller offer",
        target="Labelled software target", criteria=(Criterion(id="ai", description="AI software"),)), "dynamic-key")
    key = SecretStr("tvly-labelled-worker-dynamic-fixture")
    LocalCredentials(settings.db_path).save(key)
    received = []
    def execute(scoped, configuration, run_id):
        received.append((run_id, configuration.tavily_key))
    monkeypatch.setattr("shortlist.worker.execute_run", execute)
    work(settings, once=True)
    assert received == [(identity, key)]
    assert settings.tavily_key.get_secret_value() == ""
    assert not store.worker_online()


@pytest.mark.parametrize("committed", [False, True])
def test_real_process_death_recovers_the_last_committed_private_key(tmp_path, committed):
    credentials = LocalCredentials(tmp_path / "research.sqlite3")
    credentials.save(SecretStr("tvly-labelled-before-crash"))
    script = """
import os, sqlite3, sys
from pathlib import Path
from pydantic import SecretStr
from shortlist.local_credentials import LocalCredentials, _dpapi
store = LocalCredentials(Path(sys.argv[1]))
if sys.argv[2] == 'committed':
    store.save(SecretStr('tvly-labelled-after-crash'))
else:
    plain = b'tvly-labelled-after-crash'
    payload = b'SHORTLIST-DPAPI1\\n' + _dpapi(plain, decrypt=False) if os.name == 'nt' else b'SHORTLIST-PRIVATE1\\n' + plain
    db = sqlite3.connect(store.path)
    db.execute('BEGIN IMMEDIATE')
    db.execute('UPDATE local_provider SET payload=? WHERE id=1', (payload,))
os._exit(65)
"""
    result = subprocess.run([sys.executable, "-c", script, str(tmp_path / "research.sqlite3"),
                             "committed" if committed else "uncommitted"], check=False,
                            capture_output=True, text=True, timeout=10)
    assert result.returncode == 65, result.stderr
    expected = "tvly-labelled-after-crash" if committed else "tvly-labelled-before-crash"
    assert credentials.read().get_secret_value() == expected
    if os.name == "nt":
        for path in tmp_path.glob("*.providers*"):
            assert b"tvly-labelled" not in path.read_bytes()


@pytest.mark.skipif(os.name == "nt", reason="Portable symlink boundary; Windows privilege may be unavailable")
def test_symlink_provider_file_is_not_read_or_overwritten(tmp_path):
    credentials = LocalCredentials(tmp_path / "research.sqlite3")
    target = tmp_path / "missing-target"
    credentials.path.symlink_to(target)
    with pytest.raises(CredentialUnavailable):
        credentials.read()
    with pytest.raises(CredentialUnavailable):
        credentials.save(SecretStr("tvly-labelled-symlink-fixture"))
    assert not target.exists()
