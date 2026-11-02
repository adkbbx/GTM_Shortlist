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


def test_a_posting_missing_from_the_answer_is_taken_from_the_search_results():
    from shortlist.agent.discovery import with_posting

    item = CandidateAnswer(name="Trail Gear", domain="trailgear.example", found_via="job post on jobs.lever.co")
    results = ["https://jobs.lever.co/othergear/x-1", "https://jobs.lever.co/TrailGear/aaa-111", "https://trailgear.example/"]
    assert with_posting(item, results).posting_url == "https://jobs.lever.co/TrailGear/aaa-111"
    assert with_posting(item, ["https://jobs.lever.co/othergear/x-1"]).posting_url == ""
    several = ["https://jobs.lever.co/trailgear/data-1", "https://jobs.lever.co/trailgear/aaa-111"]
    assert with_posting(item, several).posting_url == "https://jobs.lever.co/trailgear"  # chosen by title later


def test_a_posting_page_that_cannot_be_read_is_built_from_the_boards_own_text():
    ashby = {"jobs": [{"title": "Founding SDR", "jobUrl": "https://jobs.ashbyhq.com/trailgear/abc-1", "isListed": True,
                       "location": "Remote", "publishedAt": "2026-10-20T09:00:00.000+00:00",
                       "descriptionHtml": "<p>Trailgear is hiring its first SDR to build outbound from zero.</p>"}]}

    def handle(request):
        if request.url.host == "api.ashbyhq.com" and request.url.path.endswith("/trailgear"):
            return httpx.Response(200, json=ashby)
        return httpx.Response(404)
    built = JobBoards(transport=httpx.MockTransport(handle)).page_for("https://jobs.ashbyhq.com/trailgear/abc-1")
    assert "hiring its first SDR to build outbound from zero" in built.full_text
    assert built.url == "https://jobs.ashbyhq.com/trailgear/abc-1" and built.dates == (date(2026, 10, 20),)
    assert JobBoards(transport=httpx.MockTransport(handle)).page_for("https://jobs.ashbyhq.com/trailgear/gone") is None


def test_a_bare_board_url_finds_the_matching_role_and_old_greenhouse_links_are_rewritten():
    from shortlist.agent.jobboards import posting_page

    item = CandidateAnswer(name="Trailgear", domain="trailgear.example", posting_url="https://jobs.lever.co/trailgear",
                           found_via="job post: Sales Manager (US) to build the US market (Lever, Oct 2026)")
    assert "Sales Manager (US)" in lead(item, boards(), lambda *a, **k: None)
    vague = item.model_copy(update={"found_via": "job post: Data Engineer (Lever)"})
    assert "not confirmed open" in lead(vague, boards(), lambda *a, **k: None)
    assert posting_page("https://boards.greenhouse.io/acme/jobs/12") == "https://job-boards.greenhouse.io/acme/jobs/12"
    assert posting_page("https://jobs.lever.co/acme/1") == "https://jobs.lever.co/acme/1"


def test_the_posting_discovery_confirmed_open_is_handed_to_the_investigator():
    """Live runs confirmed an open, dated posting and still ended "No current need": the investigator quoted the
    board's heading (rescale.com) or never fetched it. Its text is now read from the board and put in the brief."""
    from types import SimpleNamespace

    from shortlist.agent.investigation import Investigation
    from shortlist.agent.models import CandidateRef
    from shortlist.agent.pages import open_posting, verified_date

    posting_id = "0acd1fa9-c3ce-4e84-a5bf-17ec707ab8e5"
    url = f"https://jobs.lever.co/trailgear/{posting_id}"
    one = {"text": "Support Lead", "hostedUrl": url, "createdAt": 1793000000000, "descriptionPlain": "Trailgear",
           "description": "<p>Trailgear (SYNTHETIC) is hiring a support lead to answer customer chats and emails.</p>"}
    reader = JobBoards(transport=httpx.MockTransport(
        lambda request: httpx.Response(200, json=one) if posting_id in request.url.path else httpx.Response(404)))
    events = []
    ctx = SimpleNamespace(job_boards=reader, emit=lambda *args, **kwargs: events.append(args[1]))
    via = f"open job post on its Lever board: Support Lead, posted 2026-10-26 ({url})"
    investigation = Investigation(CandidateRef(domain="trailgear.example", name="Trailgear", url="https://trailgear.example/",
                                               found_via=via), ctx)
    investigation.read_lead_posting()
    page = investigation.posting
    assert page.url == url and open_posting(page) and verified_date(None, page) == date(2026, 10, 26)
    assert investigation.pages[url] is page and events == ["Read the open posting: Support Lead"]

    unconfirmed = Investigation(CandidateRef(domain="trailgear.example", name="Trailgear", url="https://trailgear.example/",
                                             found_via=f"job post: Support Lead ({url} not confirmed open)"), ctx)
    unconfirmed.read_lead_posting()
    assert unconfirmed.posting is None  # only a posting discovery confirmed open is handed over


def test_smartrecruiters_boards_are_read_like_the_others():
    """A fourth board system with a public job list (checked live on 2 November): titles and dates in the list, the
    description from the single posting."""
    listing = {"content": [{"id": "744000158015889", "name": "Customer Support Representative",
                            "releasedDate": "2026-10-27T09:00:00.000Z", "location": {"fullLocation": "Remote"},
                            "company": {"name": "Trailgear"}}]}
    one = {**listing["content"][0], "postingUrl": "https://jobs.smartrecruiters.com/trailgear/744000158015889-support",
           "jobAd": {"sections": {"jobDescription": {"title": "Job Description",
                                                     "text": "<p>Trailgear (SYNTHETIC) needs a support rep for chat.</p>"}}}}

    def handle(request):
        if request.url.path == "/v1/companies/trailgear/postings":
            return httpx.Response(200, json=listing)
        if request.url.path == "/v1/companies/trailgear/postings/744000158015889":
            return httpx.Response(200, json=one)
        return httpx.Response(404, json={})
    reader = JobBoards(transport=httpx.MockTransport(handle))
    assert board_refs('<a href="https://careers.smartrecruiters.com/Trailgear">Jobs</a>') == [("smartrecruiters", "trailgear")]
    board = reader.read("smartrecruiters", "trailgear")
    assert (board.label, board.openings[0].title, board.openings[0].posted) == (
        "SmartRecruiters", "Customer Support Representative", date(2026, 10, 27))
    url = "https://jobs.smartrecruiters.com/trailgear/744000158015889-support"
    board, opening = reader.posting(url, ["Trailgear"])
    assert opening.posted == date(2026, 10, 27)
    page = reader.page_for(url)
    assert page is not None and "support rep for chat" in page.source.text


def test_one_posting_is_read_on_its_own_so_a_large_board_cannot_hide_it():
    """AHEAD's Lever list was 4 MB, over the reader's cap, so its open posting showed as "not confirmed open". A
    Lever or Greenhouse posting is now asked for by its own id; a closed one answers 404."""
    posting_id = "1ffb36db-8d38-497e-8eb6-21ad13889464"
    one = {"text": "Senior AI Engineer", "hostedUrl": f"https://jobs.lever.co/bigboard/{posting_id}",
           "createdAt": 1764806400000, "descriptionPlain": "Bigboard (SYNTHETIC) is hiring.", "description": "<p>Role</p>"}
    requests = []

    def handle(request):
        requests.append(request.url.path)
        if request.url.path == f"/v0/postings/bigboard/{posting_id}":
            return httpx.Response(200, json=one)
        if request.url.path == "/v0/postings/bigboard":
            return httpx.Response(200, content=b"[" + b" " * 13_000_000 + b"]")  # too large to read whole
        return httpx.Response(404, json={"ok": False})
    reader = JobBoards(transport=httpx.MockTransport(handle))
    board, opening = reader.posting(f"https://jobs.lever.co/bigboard/{posting_id}", ["Bigboard"])
    assert (board.label, opening.title, opening.posted) == ("Lever", "Senior AI Engineer", date(2025, 12, 4))
    assert requests == [f"/v0/postings/bigboard/{posting_id}"]  # the whole list was never needed
    assert reader.page_for(f"https://jobs.lever.co/bigboard/{posting_id}") is not None
    closed = "https://jobs.lever.co/bigboard/00000000-0000-0000-0000-000000000000"
    assert reader.posting(closed, ["Bigboard"]) is None and reader.page_for(closed) is None
