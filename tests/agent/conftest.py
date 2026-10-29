"""Agent tests use only the LABELLED SYNTHETIC world in shortlist.agent.synthetic: no network, no provider keys."""
from datetime import date

import pytest

from shortlist.agent.pipeline import AgentRunner
from shortlist.agent.synthetic import SELLER, synthetic_providers

TODAY = date(2026, 10, 29)


@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    """Any attempt to reach a real website or provider fails the test."""
    def refuse(*args, **kwargs):
        raise AssertionError("Agent tests must not open network connections")
    monkeypatch.setattr("socket.create_connection", refuse)
    monkeypatch.setattr("socket.getaddrinfo", refuse)


@pytest.fixture
def providers():
    return synthetic_providers(TODAY)


@pytest.fixture
def events():
    return []


@pytest.fixture
def run_result(providers, events):
    return AgentRunner(providers, on_event=events.append).run(SELLER)
