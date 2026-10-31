"""Job boards first (1 November): live runs lost open roles to job sites that blocked the fetch or had dropped the
post, while the company's own Lever board still listed it. Board answers here are SYNTHETIC, shaped like the public
Lever, Greenhouse and Ashby job lists; companies are on reserved .example domains."""
from datetime import date

import httpx

from shortlist.agent.answers import CandidateAnswer
from shortlist.agent.discovery import lead
from shortlist.agent.jobboards import Board, JobBoards, Opening, board_refs
from shortlist.agent.pages import page_from_document
from shortlist.agent.pipeline import AgentRunner
from shortlist.agent.synthetic import SELLER
from shortlist.fetch import FetchError

LEVER = [
    {"text": "Sales Manager (US)", "hostedUrl": "https://jobs.lever.co/trailgear/aaa-111", "createdAt": 1793000000000,
     "categories": {"location": "Chicago"}, "descriptionPlain": "Trailgear is a seed-stage logistics startup."},
    {"text": "Not on Lever", "hostedUrl": "https://evil.example/job", "descriptionPlain": ""},
]
GREENHOUSE = {"jobs": [{"title": "Founding SDR", "absolute_url": "https://job-boards.greenhouse.io/otherco/jobs/9",
                        "location": {"name": "Remote"}, "first_published": "2026-10-20T09:00:00-04:00",
                        "content": "&lt;p&gt;About OtherCo, a chain protocol&lt;/p&gt;"}]}


def boards(requests=None):
    def handle(request):
        if requests is not None:
            requests.append(str(request.url))
        if request.url.host == "api.lever.co" and request.url.path.endswith("/trailgear"):
            return httpx.Response(200, json=LEVER)
        if request.url.host == "boards-api.greenhouse.io" and "/otherco/" in request.url.path:
            return httpx.Response(200, json=GREENHOUSE)
        return httpx.Response(404, json={"ok": False})
    return JobBoards(transport=httpx.MockTransport(handle))


def page(url, body):
    filler = "<p>Synthetic page: Trailgear builds route planning software for small freight teams.</p>"
    return page_from_document(url, (filler + body).encode(), None)


def test_boards_are_found_in_links_and_embeds_only():
    text = ('<a href="https://jobs.lever.co/TrailGear/">Jobs</a> '
            '<script src="https://boards.greenhouse.io/embed/job_board/js?for=otherco"></script> '
            '<a href="https://jobs.ashbyhq.com/acme/123">Role</a>')
    assert board_refs(text) == [("lever", "trailgear"), ("greenhouse", "otherco"), ("ashby", "acme")]


def test_a_board_is_read_from_the_public_job_list():
    board = boards().read("lever", "trailgear")
    assert board.openings == (Opening(title="Sales Manager (US)", url="https://jobs.lever.co/trailgear/aaa-111",
                                      location="Chicago", posted=date(2026, 10, 26)),)  # the off-board link is dropped
    assert board.url == "https://jobs.lever.co/trailgear" and "seed-stage" in board.text
    assert boards().read("lever", "nobody") is None


def test_own_board_comes_from_the_companys_site_never_from_its_name():
    linked = page("https://trailgear.example/", '<a href="https://jobs.lever.co/trailgear">Careers</a>')
    assert boards().own(linked, fetch=lambda url: None).slug == "trailgear"

    careers = page("https://trailgear.example/careers", '<iframe src="https://jobs.lever.co/trailgear"></iframe>')
    home = page("https://trailgear.example/", '<a href="/careers">We are hiring</a>')
    assert boards().own(home, fetch=lambda url: careers).openings[0].title == "Sales Manager (US)"

    def unreadable(url):
        raise FetchError("Redirect changed company identity; manual verification required")

    def handle(request):
        if request.url.host == "trailgear.example":
            return httpx.Response(302, headers={"location": "https://jobs.lever.co/trailgear"})
        if request.url.host == "api.lever.co":
            return httpx.Response(200, json=LEVER)
        return httpx.Response(404)
    redirecting = JobBoards(transport=httpx.MockTransport(handle))
    assert redirecting.own(home, fetch=unreadable).slug == "trailgear"

    requests = []
    bare = page("https://trailgear.example/", "<p>Trailgear</p>")
    assert boards(requests).own(bare, fetch=lambda url: None) is None
    assert requests == []  # no guessing jobs.lever.co/trailgear from the name


def test_a_discovered_posting_counts_only_when_still_listed_on_a_board_that_names_the_company():
    item = CandidateAnswer(name="Trailgear", domain="trailgear.example", found_via="job post: Sales Manager",
                           posting_url="https://jobs.lever.co/trailgear/aaa-111")
    events = []
    via = lead(item, boards(), lambda *a, **k: events.append(a))
    assert via == ("open job post on its Lever board: Sales Manager (US), posted 2026-10-26 "
                   "(https://jobs.lever.co/trailgear/aaa-111)")
    closed = item.model_copy(update={"posting_url": "https://jobs.lever.co/trailgear/gone-222"})
    assert "not confirmed open" in lead(closed, boards(), lambda *a, **k: None)
    lookalike = CandidateAnswer(name="Socket", domain="socket.example", found_via="job post: SDR",
                                posting_url="https://job-boards.greenhouse.io/otherco/jobs/9")
    assert "not confirmed open" in lead(lookalike, boards(), lambda *a, **k: None)  # OtherCo's board, not Socket's
    assert lead(item, None, lambda *a, **k: None) == "job post: Sales Manager"


class FakeBoards:
    def own(self, home, fetch):
        if home.domain == "trailgear.example":
            return Board("lever", "trailgear", (Opening("Sales Manager (US)", "https://jobs.lever.co/trailgear/aaa-111"),))
        return None

    def posting(self, url, names):
        return None


def test_the_investigation_reads_the_companys_own_board_before_its_first_model_call(providers):
    providers.job_boards = FakeBoards()
    events = []
    result = AgentRunner(providers, on_event=events.append).run(SELLER)
    trailgear = next(c for c in result.companies if c.domain == "trailgear.example")
    assert "own job board on Lever" in trailgear.checked_places
    assert any(e.message == "Read its own job board on Lever: 1 open role" for e in events)
