"""Agent HTTP routes: registered by shortlist.api.create_app in local mode (one trusted operator on loopback), and by
shortlist.agent.public for the public demo, which passes a RoutePolicy with its limits."""
import asyncio
import json
import re
from datetime import datetime
from pathlib import Path
from typing import Annotated

from fastapi import FastAPI, Header, HTTPException, Request
from fastapi.responses import Response, StreamingResponse
from pydantic import BaseModel, ConfigDict, Field
from starlette.concurrency import run_in_threadpool

from shortlist.agent.export import shortlist_csv
from shortlist.agent.models import AgentEvent, Overrides, RunResult, RunStatus
from shortlist.agent.providers import AgentProviderError
from shortlist.agent.service import ACTIVE, AgentService, RunConflict, UnknownCompany
from shortlist.agent.storage import SQLiteAgentRuns
from shortlist.fetch import FetchError


class PreviousRun(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str = Field(pattern=r"^[0-9a-f]{32}$")
    token: str = Field(max_length=128)


class AgentStartInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    website: str = Field(min_length=3, max_length=300)
    overrides: Overrides | None = None
    # Cloudflare Turnstile token; only the public demo asks for one.
    turnstile: str | None = Field(default=None, max_length=4096)
    # Public demo: this browser's earlier searches with their edit tokens, so a new search skips companies it already
    # researched for the same website without seeing anyone else's searches.
    previous: list[PreviousRun] = Field(default_factory=list, max_length=30)


class AgentStarted(BaseModel):
    id: str
    status: RunStatus
    # Public demo only: lets the browser that started a run correct it; anyone with the link can still read it.
    edit_token: str | None = None


class AgentRunView(BaseModel):
    id: str
    status: RunStatus
    created_at: datetime
    updated_at: datetime
    run: RunResult
    events: list[AgentEvent]


class AgentRunSummary(BaseModel):
    id: str
    created_at: datetime
    status: RunStatus
    website: str
    synthetic: bool = False
    shortlisted: int = 0
    needs_look: int = 0
    rejected: int = 0


class RoutePolicy:
    """Checks around starting and correcting runs. The default trusts the local operator; the public demo overrides it."""
    listing = True

    def before_start(self, request: Request, body: AgentStartInput) -> AgentStartInput:
        return body

    def started(self, result: RunResult) -> str | None:
        return None

    def before_email(self, request: Request, run_id: str) -> None:
        return None

    def history_runs(self, body: AgentStartInput) -> list[str] | None:
        """Runs whose companies a new search sets aside; None uses the whole store's history (local mode)."""
        return None

    def before_override(self, request: Request, run_id: str, overrides: Overrides, current: RunResult) -> Overrides:
        return overrides


def register_agent_routes(app: FastAPI, db_path: Path | None, service: AgentService | None = None,
                          policy: RoutePolicy | None = None) -> AgentService:
    service = service or AgentService(SQLiteAgentRuns(db_path))
    policy = policy or RoutePolicy()
    app.state.agent_service = service

    def view(run_id: str) -> AgentRunView:
        record = service.store.get(run_id)
        return AgentRunView(id=record["id"], status=record["status"], created_at=record["created_at"],
                            updated_at=record["updated_at"], run=record["result"], events=record["events"])

    @app.post("/api/agent/runs", response_model=AgentStarted, status_code=201, tags=["agent"])
    def start_agent_run(body: AgentStartInput, request: Request):
        body = policy.before_start(request, body)
        try:
            result = service.start(body.website, body.overrides, history_runs=policy.history_runs(body))
        except FetchError as exc:
            raise HTTPException(422, str(exc)) from exc
        return AgentStarted(id=result.id, status=result.status, edit_token=policy.started(result))

    @app.get("/api/agent/runs", response_model=list[AgentRunSummary], tags=["agent"])
    def list_agent_runs():
        return service.store.list(20) if policy.listing else []

    @app.get("/api/agent/runs/{run_id}", response_model=AgentRunView, tags=["agent"])
    def read_agent_run(run_id: str):
        return view(run_id)

    @app.get("/api/agent/runs/{run_id}/shortlist.csv", tags=["agent"], response_class=Response,
             responses={200: {"content": {"text/csv": {}}, "description": "One row per decided company"}})
    def export_agent_run(run_id: str):
        result: RunResult = service.store.get(run_id)["result"]
        domain = re.sub(r"[^a-z0-9.-]", "", result.website.split("//")[-1].split("/")[0].lower().removeprefix("www."))
        name = f"shortlist-{domain or 'search'}-{result.created_at:%Y-%m-%d}.csv"
        return Response("\ufeff" + shortlist_csv(result), media_type="text/csv; charset=utf-8",
                        headers={"Content-Disposition": f'attachment; filename="{name}"'})

    @app.post("/api/agent/runs/{run_id}/companies/{domain}/outreach", response_model=AgentRunView, tags=["agent"])
    def draft_agent_email(run_id: str, domain: str, request: Request):
        policy.before_email(request, run_id)
        try:
            service.draft_email(run_id, domain)
        except UnknownCompany as exc:  # a missing search raises KeyError: the app's "search not found" answer
            raise HTTPException(404, "This company is not in this search.") from exc
        except RunConflict as exc:
            raise HTTPException(409, str(exc)) from exc
        except AgentProviderError as exc:
            raise HTTPException(503, str(exc)) from exc
        return view(run_id)

    @app.post("/api/agent/runs/{run_id}/overrides", response_model=AgentRunView, status_code=202, tags=["agent"])
    def override_agent_run(run_id: str, body: Overrides, request: Request):
        body = policy.before_override(request, run_id, body, service.store.get(run_id)["result"])
        try:
            service.override(run_id, body)
        except RunConflict as exc:
            raise HTTPException(409, str(exc)) from exc
        return view(run_id)

    @app.get("/api/agent/runs/{run_id}/events", tags=["agent"], response_class=StreamingResponse,
             responses={200: {"content": {"text/event-stream": {}},
                              "description": "Server-Sent Events: progress events, then one end event"}})
    async def agent_run_events(run_id: str, request: Request, after: int = 0,
                               last_event_id: Annotated[str | None, Header()] = None):
        await run_in_threadpool(service.store.get, run_id)
        start = int(last_event_id) if last_event_id and last_event_id.isdigit() else max(after, 0)

        async def stream():
            sent, quiet = start, 0.0
            yield "retry: 2000\n\n"
            while True:
                status, events = await run_in_threadpool(service.store.events, run_id, sent)
                for event in events:
                    sent = event.seq
                    yield f"id: {event.seq}\nevent: progress\ndata: {event.model_dump_json()}\n\n"
                if status not in ACTIVE:
                    yield f"event: end\ndata: {json.dumps({'status': status})}\n\n"
                    return
                if await request.is_disconnected():
                    return
                await asyncio.sleep(0.4)
                quiet = 0.0 if events else quiet + 0.4
                if quiet >= 15:
                    quiet = 0.0
                    yield ": keep-alive\n\n"

        return StreamingResponse(stream(), media_type="text/event-stream",
                                 headers={"Cache-Control": "no-store", "X-Accel-Buffering": "no"})

    return service
