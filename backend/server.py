"""Web API around leash.demo: runs the demo in a thread, buffers its events, and relays approvals."""

import json
import os
import sys
import threading
import traceback
import uuid
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(Path(__file__).resolve().parent / ".env")
sys.path.insert(0, str(ROOT))

from fastapi import APIRouter, FastAPI, HTTPException  # noqa: E402
from fastapi.middleware.cors import CORSMiddleware  # noqa: E402
from pydantic import BaseModel  # noqa: E402

from leash import agent as agent_module  # noqa: E402
from leash.agent import Agent  # noqa: E402
from leash.client import AirwallexClient  # noqa: E402
from leash.demo import Config, Demo  # noqa: E402
from main import AUTO_ANSWERS  # noqa: E402


def _env(name: str) -> str:
    # Values pasted with surrounding quotes, as in the README's .env example, are unquoted.
    return os.environ.get(name, "").strip().strip('"').strip("'")


class Run:
    def __init__(self, auto: bool):
        self.id = uuid.uuid4().hex[:12]
        self.auto = auto
        self.started_at = datetime.now(timezone.utc).isoformat()
        self.status = "running"
        self.events: list[dict] = []
        self.pending: dict | None = None
        self.error: str | None = None
        self._answers = iter(AUTO_ANSWERS)
        self._answer: bool | None = None
        self._decided = threading.Event()
        self._lock = threading.Lock()

    def emit(self, kind: str, **e) -> None:
        event = json.loads(json.dumps({"event": kind, **e}, default=str))
        with self._lock:
            self.events.append(event)

    def ask(self, request: dict) -> bool:
        if self.auto:
            return next(self._answers, False)
        self._decided.clear()
        self.pending = json.loads(json.dumps(request, default=str))
        self.status = "waiting_approval"
        self._decided.wait()
        self.pending = None
        self.status = "running"
        return bool(self._answer)

    def answer(self, approved: bool) -> None:
        self._answer = approved
        self._decided.set()

    def execute(self) -> None:
        try:
            email = _env("LEASH_CARDHOLDER_EMAIL")
            created_by = _env("LEASH_CREATED_BY")
            if not email or not created_by:
                raise SystemExit("Set LEASH_CARDHOLDER_EMAIL and LEASH_CREATED_BY")
            config = Config(cardholder_email=email, created_by=created_by, approver=created_by)
            Demo(AirwallexClient.from_env(), Agent(), config, self.emit, self.ask).run()
            self.status = "done"
        except BaseException as exc:  # SystemExit is how the demo stops early
            self.error = str(exc) or exc.__class__.__name__
            traceback.print_exc()
            self.emit("error", text=self.error)
            self.status = "failed"

    def snapshot(self, after: int = 0) -> dict:
        with self._lock:
            events = self.events[after:]
            total = len(self.events)
        return {"id": self.id, "auto": self.auto, "started_at": self.started_at, "status": self.status,
                "pending": self.pending, "error": self.error, "total": total, "after": after, "events": events}


runs: dict[str, Run] = {}
latest: list[str] = []

app = FastAPI()
api = APIRouter(prefix="/api")


class StartRun(BaseModel):
    auto: bool = False


class Decision(BaseModel):
    approved: bool
    digest: str


def _get(run_id: str) -> Run:
    run = runs.get(run_id)
    if run is None:
        raise HTTPException(404, "run not found")
    return run


@api.get("/health")
def health():
    return {
        "ok": True,
        "airwallex_configured": bool(os.environ.get("AIRWALLEX_CLIENT_ID") and (os.environ.get("AIRWALLEX_API_KEY") or os.environ.get("AIRWALLEX_API"))),
        "cardholder_configured": bool(os.environ.get("LEASH_CARDHOLDER_EMAIL") and os.environ.get("LEASH_CREATED_BY")),
        "llm": "emergent" if agent_module.USE_EMERGENT else "anthropic",
        "model": agent_module.MODEL,
    }


@api.post("/runs")
def start_run(body: StartRun):
    if latest and runs[latest[-1]].status in ("running", "waiting_approval"):
        raise HTTPException(409, "a run is already in progress")
    run = Run(body.auto)
    runs[run.id] = run
    latest.append(run.id)
    threading.Thread(target=run.execute, daemon=True).start()
    return run.snapshot()


@api.get("/runs/latest")
def latest_run():
    return runs[latest[-1]].snapshot() if latest else None


@api.get("/runs/{run_id}")
def get_run(run_id: str, after: int = 0):
    return _get(run_id).snapshot(after)


@api.post("/runs/{run_id}/approval")
def decide(run_id: str, body: Decision):
    run = _get(run_id)
    if run.pending is None:
        raise HTTPException(409, "no approval is pending")
    if body.digest != run.pending["digest"]:
        raise HTTPException(409, "this approval is no longer the pending one")
    run.answer(body.approved)
    return {"ok": True}


app.include_router(api)
app.add_middleware(
    CORSMiddleware,
    allow_origins=os.environ.get("CORS_ORIGINS", "*").split(","),
    allow_methods=["*"],
    allow_headers=["*"],
)
