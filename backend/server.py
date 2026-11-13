"""Web API around leash.demo: runs the demo in a thread, streams its events, relays approvals and keeps every run."""

import io
import json
import os
import secrets
import sys
import tempfile
import threading
import traceback
import uuid
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(Path(__file__).resolve().parent / ".env")
sys.path.insert(0, str(ROOT))

from fastapi import APIRouter, FastAPI, File, HTTPException, Request, UploadFile  # noqa: E402
from fastapi.middleware.cors import CORSMiddleware  # noqa: E402
from fastapi.responses import JSONResponse, StreamingResponse  # noqa: E402
from pydantic import BaseModel, Field  # noqa: E402
from pypdf import PdfReader  # noqa: E402
from pymongo import MongoClient  # noqa: E402

from leash import agent as agent_module  # noqa: E402
from leash import demo as demo_module  # noqa: E402
from leash.agent import Agent  # noqa: E402
from leash.client import AirwallexClient  # noqa: E402
from leash.demo import Config, Demo  # noqa: E402
from main import AUTO_ANSWERS  # noqa: E402

ACTIVE = ("running", "waiting_approval")
EXAMPLE_QUOTES = demo_module.QUOTES_DIR
MAX_QUOTE_BYTES = 2 * 1024 * 1024
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
            s["approvals"][-1].update(approved=e["approved"], note=e.get("note"))
        elif kind in ("charge", "checkout"):
            s["rows"] += 1
            s["unexpected"] += 0 if e["as_expected"] else 1
    return s


def _public(doc: dict) -> dict:
    return {key: doc.get(key) for key in ("seq", "auto", "started_at", "finished_at", "status", "error", "model", "summary", "quote_source", "share_token")} | {"id": doc["_id"]}


class WebDemo(Demo):
    """Same scenes; the price-change scene is left out when an own quote comes without a follow-up email."""

    skip_price_change = False

    def price_increase(self) -> None:
        if not self.skip_price_change:
            super().price_increase()


class Run:
    def __init__(self, auto: bool, quote_text: str | None = None, increase_text: str | None = None):
        self.id = uuid.uuid4().hex[:12]
        self.auto = auto
        self.quote_text = quote_text
        self.increase_text = increase_text
        self._note = ""
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
            "quote_source": "own" if quote_text else "example", "share_token": None,
        })

    def emit(self, kind: str, **e) -> None:
        event = json.loads(json.dumps({"event": kind, **e}, default=str)) | {"at": _now()}
        if kind == "approval_result" and self._note:
            event["note"], self._note = self._note, ""
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

    def answer(self, approved: bool, note: str) -> None:
        with self._cond:
            self.pending = None
        self._answer, self._note = approved, note.strip()
        self._decided.set()

    def execute(self) -> None:
        try:
            email = _env("LEASH_CARDHOLDER_EMAIL")
            created_by = _env("LEASH_CREATED_BY")
            if not email or not created_by:
                raise SystemExit("Set LEASH_CARDHOLDER_EMAIL and LEASH_CREATED_BY")
            config = Config(cardholder_email=email, created_by=created_by, approver=created_by)
            demo = WebDemo(AirwallexClient.from_env(), Agent(), config, self.emit, self.ask)
            if self.quote_text is None:
                demo.run()
            else:
                self._run_own_quote(demo)
            self._set("done")
        except BaseException as exc:  # SystemExit is how the demo stops early
            self.error = str(exc) or exc.__class__.__name__
            traceback.print_exc()
            self.emit("error", text=self.error)
            self._set("failed")

    def _run_own_quote(self, demo: WebDemo) -> None:
        # leash.demo reads its quotes from QUOTES_DIR; point it at this purchase's emails for the one live run.
        demo.skip_price_change = not self.increase_text
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp) / "northwind.txt").write_text(self.quote_text)
            if self.increase_text:
                (Path(tmp) / "northwind_increase.txt").write_text(self.increase_text)
            demo_module.QUOTES_DIR = Path(tmp)
            try:
                demo.run()
            finally:
                demo_module.QUOTES_DIR = EXAMPLE_QUOTES

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
    quote_text: str | None = Field(default=None, min_length=20, max_length=20000)
    increase_text: str | None = Field(default=None, max_length=20000)


class Decision(BaseModel):
    approved: bool
    digest: str
    note: str = Field(default="", max_length=280)


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
        "quote_text": (EXAMPLE_QUOTES / "northwind.txt").read_text(),
        "merchant_category": demo_module.SAAS_MCC,
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
    run = Run(body.auto, body.quote_text, (body.increase_text or "").strip() or None)
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
    run.answer(body.approved, body.note)
    return {"ok": True}


@api.post("/quotes/extract")
async def extract_quote(file: UploadFile = File(...)):
    """Text of an uploaded quote: PDF text is extracted, anything else must be plain text."""
    data = await file.read(MAX_QUOTE_BYTES + 1)
    if len(data) > MAX_QUOTE_BYTES:
        raise HTTPException(413, "That file is larger than 2 MB.")
    if data[:5] == b"%PDF-":
        try:
            text = "\n".join(page.extract_text() or "" for page in PdfReader(io.BytesIO(data)).pages)
        except Exception:
            raise HTTPException(422, "That PDF could not be read. Paste the quote text instead.")
        if not text.strip():
            raise HTTPException(422, "That PDF has no selectable text (it looks scanned). Paste the quote text instead.")
    else:
        try:
            text = data.decode("utf-8")
        except UnicodeDecodeError:
            raise HTTPException(422, "That file is not plain text or a PDF. Paste the quote text instead.")
    return {"text": text.strip(), "filename": file.filename}


@api.get("/runs/{run_id}/export")
def export_run(run_id: str):
    snap = _snapshot(run_id)
    events = snap.pop("events")
    for key in ("pending", "total", "after", "share_token"):
        snap.pop(key)
    return JSONResponse({"purchase": snap, "exported_at": _now(), "events": events},
                        headers={"Content-Disposition": f'attachment; filename="leash-purchase-{snap["seq"]}.json"'})


@api.post("/runs/{run_id}/share")
def share_run(run_id: str):
    snap = _snapshot(run_id)
    if snap["status"] in ACTIVE:
        raise HTTPException(409, "a purchase can be shared once it has finished")
    token = snap["share_token"] or secrets.token_urlsafe(16)
    db.runs.update_one({"_id": run_id}, {"$set": {"share_token": token}})
    return {"token": token}


@api.delete("/runs/{run_id}/share")
def unshare_run(run_id: str):
    _snapshot(run_id)
    db.runs.update_one({"_id": run_id}, {"$set": {"share_token": None}})
    return {"ok": True}


@api.get("/shared/{token}")
def shared_run(token: str):
    doc = db.runs.find_one({"share_token": token}, {"_id": 1})
    if doc is None:
        raise HTTPException(404, "this link is not active")
    return _snapshot(doc["_id"]) | {"share_token": None}


app.include_router(api)
app.add_middleware(
    CORSMiddleware,
    allow_origins=os.environ.get("CORS_ORIGINS", "*").split(","),
    allow_methods=["*"],
    allow_headers=["*"],
)
