import hashlib
from concurrent.futures import ThreadPoolExecutor

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from shortlist.api import create_app
from shortlist.config import Settings
from shortlist.domain import Criterion, Profile, Source
from shortlist.providers import validate_extraction
from shortlist.store import Conflict, Store


@pytest.mark.parametrize("url", ["http://cal.example/setup", "javascript:alert(1)", "https://localhost/setup",
                                 "https://127.0.0.1/", "https://user:password@cal.example/setup"])
def test_booking_configuration_rejects_unsafe_destinations(url):
    with pytest.raises(ValidationError):
        Settings(booking_url=url)


def test_optional_booking_records_clicks_not_appointments_or_credits(tmp_path):
    settings = Settings(db_path=tmp_path / "booking.sqlite3", booking_url="https://cal.example/setup")
    store = Store(settings.db_path)
    client = TestClient(create_app(settings))
    assert client.get("/api/service").json() == {"booking_url": "https://cal.example/setup"}
    profile = Profile(seller_url="https://seller.example/", offer="Seller research fixture",
                      target="Business software", criteria=(Criterion(id="software", description="Offers software"),))
    identity = store.create_run(profile, "booking-run")
    with pytest.raises(Conflict):
        store.booking_click(identity, "not-finished")
    fence = store.claim(identity)
    text = "Company software fixture."
    source = Source(url="https://company.example/", company_domain="company.example", title="Booking fixture",
                    text=text, content_hash=hashlib.sha256(text.encode()).hexdigest())
    record = validate_extraction({"name": "Fixture", "findings": [{"criterion_id": "software", "status": "unknown",
                                  "reason": "Fixture has insufficient evidence"}]}, profile, source.company_domain, (source,))
    store.save_record(identity, fence, record)
    store.checkpoint(identity, fence, "complete", {}, "partial")
    with ThreadPoolExecutor(max_workers=6) as pool:
        list(pool.map(lambda _: store.booking_click(identity, "same-click-key"), range(6)))
    assert client.post(f"/api/runs/{identity}/booking-click", json={"request_key": "same-click-key"}).status_code == 204
    assert client.post(f"/api/runs/{identity}/booking-click", json={"request_key": "fake-booked", "booked": True}).status_code == 422
    with store.connection() as db:
        assert db.execute("SELECT count(*) FROM booking_clicks").fetchone()[0] == 1
    unconfigured = TestClient(create_app(Settings(db_path=store.path)))
    assert unconfigured.get("/api/service").json() == {"booking_url": None}
    assert unconfigured.post(f"/api/runs/{identity}/booking-click", json={"request_key": "new-click"}).status_code == 409
    store.delete_run(identity)
    with store.connection() as db:
        assert db.execute("SELECT count(*) FROM booking_clicks").fetchone()[0] == 0
    assert client.post(f"/api/runs/{identity}/booking-click", json={"request_key": "after-delete"}).status_code == 404
