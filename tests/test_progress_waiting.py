"""A wait for the user that later work followed reads as answered, not as still waiting."""
from shortlist.progress import public_events


def event(identity, phase, label, state):
    return {"id": identity, "phase": phase, "label": label, "state": state, "detail": None,
            "created_at": "2026-10-18T13:07:49+00:00"}


def test_answered_waits_read_as_done_and_the_current_wait_stays_waiting():
    waiting = event(1, "confirmation", "Ready for your offer and target confirmation", "waiting")
    later = event(2, "discovery", "Research worker picked up your saved run", "succeeded")
    answered = public_events({"events": [waiting, later], "checkpoint": {}, "records": []})
    assert answered[0]["state"] == "succeeded" and answered[0]["label"] == "You confirmed your offer and target"
    # The newest wait is still the user's turn.
    assert public_events({"events": [waiting], "checkpoint": {}, "records": []})[0]["state"] == "waiting"
    website = event(1, "seller", "Choose the website for your company", "waiting")
    assert public_events({"events": [website, later], "checkpoint": {}, "records": []})[0]["label"] == "You chose your company website"
