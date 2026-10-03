"""HTTP layer: renders the page and exposes the rules as a stateless API."""

from __future__ import annotations

import mimetypes
from datetime import UTC, datetime
from pathlib import Path
from typing import Annotated, Any

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel, Field

from screencare import messages, rules
from screencare.summary import dashboard

ROOT = Path(__file__).resolve().parent
PUBLIC = ROOT.parent / "public"

mimetypes.add_type("application/manifest+json", ".webmanifest")

app = FastAPI(title="ScreenCare", docs_url=None, redoc_url=None, openapi_url=None)
templates = Jinja2Templates(directory=ROOT / "templates")


class ActRequest(BaseModel):
    session: rules.Session = Field(default_factory=rules.Session)
    settings: rules.Settings = Field(default_factory=rules.Settings)
    action: str
    payload: dict[str, Any] = Field(default_factory=dict)


class SummaryRequest(BaseModel):
    records: Annotated[list[dict[str, Any]], Field(max_length=20_000)] = []
    tz_offset_minutes: Annotated[int, Field(ge=-840, le=840)] = 0


@app.get("/", response_class=HTMLResponse)
def index(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(
        request,
        "index.html",
        {
            "modes": [
                ("adaptive", "Adaptive", "Learns your rhythm"),
                ("classic", "Classic", "25 · 5"),
                ("deep", "Deep focus", "50 · 8"),
            ],
            "defaults": rules.Settings().model_dump(),
            "copy": messages.UI,
            "max_extensions": rules.MAX_EXTENSIONS,
        },
    )


@app.post("/api/act")
def act(body: ActRequest) -> dict[str, Any]:
    now = datetime.now(UTC)
    try:
        session, events = rules.apply(body.session, body.settings, body.action, body.payload, now)
    except rules.InvalidAction as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except (ValueError, TypeError) as exc:  # a malformed payload value (mode, timestamp, ...)
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return {"session": session, "events": events, "server_now": now}


@app.post("/api/summary")
def summary(body: SummaryRequest) -> dict[str, Any]:
    return dashboard(body.records, datetime.now(UTC), body.tz_offset_minutes)


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


# Declared last so every route above wins. On Vercel the CDN answers public/
# paths before the app sees them (and Vercel forbids mounting public/), so this
# only does work when running locally with `uvicorn app:app`.
@app.get("/{path:path}", include_in_schema=False)
def public_file(path: str) -> FileResponse:
    file = (PUBLIC / path).resolve()
    if not file.is_file() or not file.is_relative_to(PUBLIC):
        raise HTTPException(status_code=404)
    return FileResponse(file)
