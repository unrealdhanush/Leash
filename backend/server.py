"""Web API around leash.demo: runs the demo in a thread, streams its events, relays approvals and keeps every run."""

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

from fastapi import APIRouter, FastAPI, HTTPException, Request  # noqa: E402
from fastapi.middleware.cors import CORSMiddleware  # noqa: E402
from fastapi.responses import StreamingResponse  # noqa: E402
from pydantic import BaseModel  # noqa: E402
from pymongo import MongoClient  # noqa: E402

from leash import agent as agent_module  # noqa: E402
from leash import demo as demo_module  # noqa: E402
from leash.agent import Agent  # noqa: E402
from leash.client import AirwallexClient  # noqa: E402
from leash.demo import Config, Demo  # noqa: E402
from main import AUTO_ANSWERS  # noqa: E402

ACTIVE = ("running", "waiting_approval")
db = MongoClient(os.environ["MONGO_URL"])[os.environ["DB_NAME"]]


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _env(name: str) -> str:
    # Values pasted with surrounding quotes, as in the README's .env example, are unquoted.
    return os.environ.get(name, "").strip().strip('"').strip("'")


def summarize(events: list[dict]) -> dict:
    s = {"vendor": None, "chosen": None, "plan": None, "card_id": None, "card_status": None,
         "rows": 0, "unexpected": 0, "approvals": [], "scene": None}
    for e in events:
        kind = e["event"]
        if kind == "scene":
            s["scene"] = e["title"]
        elif kind == "quotes_read" and s["vendor"] is None:
            s["vendor"] = e["vendor"]
        elif kind == "decision":
            s["chosen"] = e["chosen"]
        elif kind == "card_issued":
            s.update(card_id=e["card_id"], plan=e["quote"], card_status="ACTIVE")
        elif kind == "card_updated":
            s["plan"] = e["quote"]
        elif kind == "card_status":
            s["card_status"] = e["status"]
        elif kind == "approval_request":
            s["approvals"].append({"quote": e["quote"], "reasons": e["reasons"], "approved": None})
        elif kind == "approval_result" and s["approvals"]:
            s["approvals"][-1]["approved"] = e["approved"]
        elif kind in ("charge", "checkout"):
            s["rows"] += 1
            s["unexpected"] += 0 if e["as_expected"] else 1
    return s


def _public(doc: dict) -> dict:
    return {key: doc.get(key) for key in ("seq", "auto", "started_at", "finished_at", "status", "error", "model", "summary")} | {"id": doc["_id"]}


class Run:
    def __init__(self, auto: bool):
        self.id = uuid.uuid4().hex[:12]
        self.auto = auto
        self.status = "running"
        self.events: list[dict] = []
        self.pending: dict | None = None
        self.error: str | None = None
        self._answers = iter(AUTO_ANSWERS)
        self._answer: bool | None = None
        self._decided = threading.Event()
        self._cond = threading.Condition()
        db.runs.insert_one({
            "_id": self.id, "seq": db.runs.count_documents({}) + 1, "auto": auto, "started_at": _now(), "finished_at": None,
            "status": self.status, "error": None, "model": agent_module.MODEL, "summary": summarize([]), "events": [],
        })

    def emit(self, kind: str, **e) -> None:
        event = json.loads(json.dumps({"event": kind, **e}, default=str))
        with self._cond:
            self.events.append(event)
            self._cond.notify_all()
        db.runs.update_one({"_id": self.id}, {"$push": {"events": event}, "$set": {"summary": summarize(self.events)}})

    def _set(self, status: str, pending: dict | None = None) -> None:
        with self._cond:
            self.status, self.pending = status, pending
            self._cond.notify_all()
        fields = {"status": status, "error": self.error}
        if status not in ACTIVE:
            fields["finished_at"] = _now()
        db.runs.update_one({"_id": self.id}, {"$set": fields})

    def ask(self, request: dict) -> bool:
        if self.auto:
            return next(self._answers, False)
        self._decided.clear()
        self._set("waiting_approval", json.loads(json.dumps(request, default=str)))
        self._decided.wait()
        self._set("running")
        return bool(self._answer)

    def answer(self, approved: bool) -> None:
        with self._cond:
            self.pending = None
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
            self._set("done")
        except BaseException as exc:  # SystemExit is how the demo stops early
            self.error = str(exc) or exc.__class__.__name__
            traceback.print_exc()
            self.emit("error", text=self.error)
            self._set("failed")

    def state(self) -> dict:
        return {"status": self.status, "pending": self.pending, "error": self.error}


runs: dict[str, Run] = {}
db.runs.update_many(
    {"status": {"$in": ACTIVE}},
    {"$set": {"status": "interrupted", "error": "The server restarted while this purchase was in progress.", "finished_at": _now()}},
)

app = FastAPI()
api = APIRouter(prefix="/api")


class StartRun(BaseModel):
    auto: bool = False


class Decision(BaseModel):
    approved: bool
    digest: str


def _snapshot(run_id: str, after: int = 0) -> dict:
    doc = db.runs.find_one({"_id": run_id})
    if doc is None:
        raise HTTPException(404, "run not found")
    live = runs.get(run_id)
    events = doc["events"]
    return _public(doc) | {"pending": live.pending if live else None, "total": len(events), "after": after, "events": events[after:]}


def _sse(event: str, data: dict, event_id: int | None = None) -> str:
    head = f"id: {event_id}\n" if event_id is not None else ""
    return f"{head}event: {event}\ndata: {json.dumps(data)}\n\n"


def _stream(run: Run, sent: int):
    last = None
    while True:
        with run._cond:
            run._cond.wait_for(lambda: len(run.events) > sent or run.state() != last, timeout=15)
            events, state = run.events[sent:], run.state()
        for event in events:
            sent += 1
            yield _sse("leash", event, sent)
        if state != last:
            last = state
            yield _sse("state", state)
        elif not events:
            yield ": keepalive\n\n"
        if state["status"] not in ACTIVE:
            return


@api.get("/health")
def health():
    return {
        "ok": True,
        "airwallex_configured": bool(os.environ.get("AIRWALLEX_CLIENT_ID") and (os.environ.get("AIRWALLEX_API_KEY") or os.environ.get("AIRWALLEX_API"))),
        "cardholder_configured": bool(os.environ.get("LEASH_CARDHOLDER_EMAIL") and os.environ.get("LEASH_CREATED_BY")),
        "llm": "emergent" if agent_module.USE_EMERGENT else "anthropic",
        "model": agent_module.MODEL,
    }


@api.get("/context")
def context():
    """What a purchase starts from: the vendor quote, the spending policy and the cash plan, read from leash/."""
    policy = demo_module.POLICY
    return {
        "quote_text": (demo_module.QUOTES_DIR / "northwind.txt").read_text(),
        "policy": {"auto_approve_max": policy.auto_approve_max, "reserve_floor": policy.reserve_floor,
                   "horizon_weeks": policy.horizon_weeks, "currency": policy.currency},
        "operating_cash": demo_module.OPERATING_CASH,
        "cash_plan": [{"week": f.week, "amount": f.amount, "label": f.label} for f in demo_module.CASH_PLAN],
        "approver": _env("LEASH_CREATED_BY"),
        "auto_answers": AUTO_ANSWERS,
    }


@api.get("/runs")
def list_runs():
    return [_public(doc) for doc in db.runs.find({}, {"events": 0}).sort("started_at", -1)]


@api.post("/runs")
def start_run(body: StartRun):
    if any(run.status in ACTIVE for run in runs.values()):
        raise HTTPException(409, "a run is already in progress")
    run = Run(body.auto)
    runs[run.id] = run
    threading.Thread(target=run.execute, daemon=True).start()
    return _snapshot(run.id)


@api.get("/runs/latest")
def latest_run():
    doc = db.runs.find_one({}, {"_id": 1}, sort=[("started_at", -1)])
    return _snapshot(doc["_id"]) if doc else None


@api.get("/runs/{run_id}")
def get_run(run_id: str, after: int = 0):
    return _snapshot(run_id, after)


@api.get("/runs/{run_id}/stream")
def stream_run(run_id: str, request: Request, after: int = 0):
    run = runs.get(run_id)
    if run is None:
        raise HTTPException(404, "run is not live")
    sent = int(request.headers.get("last-event-id") or after)
    return StreamingResponse(_stream(run, sent), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache, no-transform", "X-Accel-Buffering": "no"})


@api.post("/runs/{run_id}/approval")
def decide(run_id: str, body: Decision):
    run = runs.get(run_id)
    if run is None:
        if db.runs.count_documents({"_id": run_id}) == 0:
            raise HTTPException(404, "run not found")
        raise HTTPException(409, "no approval is pending")
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
