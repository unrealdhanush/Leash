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
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(Path(__file__).resolve().parent / ".env")
sys.path.insert(0, str(ROOT))

import requests  # noqa: E402
from fastapi import APIRouter, Depends, FastAPI, File, HTTPException, Request, UploadFile  # noqa: E402
from fastapi.middleware.cors import CORSMiddleware  # noqa: E402
from fastapi.responses import JSONResponse, StreamingResponse  # noqa: E402
from pydantic import BaseModel, Field  # noqa: E402
from pypdf import PdfReader  # noqa: E402
from pymongo import MongoClient, ReturnDocument  # noqa: E402

from clerk_auth import clerk_router, require_user  # noqa: E402

from leash import agent as agent_module  # noqa: E402
from leash import demo as demo_module  # noqa: E402
from leash.agent import Agent  # noqa: E402
from leash.client import AirwallexClient  # noqa: E402
from leash.demo import Config, Demo  # noqa: E402
from main import AUTO_ANSWERS  # noqa: E402

ACTIVE = ("running", "waiting_approval")
EXAMPLE_QUOTES = demo_module.QUOTES_DIR
DEFAULT_POLICY = demo_module.POLICY
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
    return {key: doc.get(key) for key in ("seq", "auto", "started_at", "finished_at", "status", "error", "model", "summary", "quote_source", "share_token", "policy", "started_by")} | {"id": doc["_id"]}


class WebDemo(Demo):
    """Same scenes; the price-change scene is left out when an own quote comes without a follow-up email."""

    skip_price_change = False

    def price_increase(self) -> None:
        if not self.skip_price_change:
            super().price_increase()


class Run:
    def __init__(self, auto: bool, quote_text: str | None, increase_text: str | None, policy, started_by: str | None):
        self.id = uuid.uuid4().hex[:12]
        self.auto = auto
        self.quote_text = quote_text
        self.increase_text = increase_text
        self.policy = policy
        self._note = ""
        self._decided_by = None
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
            "quote_source": "own" if quote_text else "example", "share_token": None, "started_by": started_by,
            "policy": {"auto_approve_max": policy.auto_approve_max, "reserve_floor": policy.reserve_floor},
        })

    def emit(self, kind: str, **e) -> None:
        event = json.loads(json.dumps({"event": kind, **e}, default=str)) | {"at": _now()}
        if kind == "approval_result":
            if self._note:
                event["note"], self._note = self._note, ""
            if self._decided_by:
                event["decided_by"], self._decided_by = self._decided_by, None
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

    def answer(self, approved: bool, note: str, decided_by: str | None) -> None:
        with self._cond:
            self.pending = None
        self._answer, self._note, self._decided_by = approved, note.strip(), decided_by
        self._decided.set()

    def execute(self) -> None:
        try:
            email = _env("LEASH_CARDHOLDER_EMAIL")
            created_by = _env("LEASH_CREATED_BY")
            if not email or not created_by:
                raise SystemExit("Set LEASH_CARDHOLDER_EMAIL and LEASH_CREATED_BY")
            config = Config(cardholder_email=email, created_by=created_by, approver=created_by)
            demo = WebDemo(AirwallexClient.from_env(), Agent(), config, self.emit, self.ask)
            self._run_with_overrides(demo)
            self._set("done")
        except BaseException as exc:  # SystemExit is how the demo stops early
            self.error = str(exc) or exc.__class__.__name__
            traceback.print_exc()
            self.emit("error", text=self.error)
            self._set("failed")

    def _run_with_overrides(self, demo: WebDemo) -> None:
        # leash.demo reads its quotes and policy from module globals; set them for the one live run, then restore.
        demo.skip_price_change = self.quote_text is not None and not self.increase_text
        with tempfile.TemporaryDirectory() as tmp:
            if self.quote_text is not None:
                (Path(tmp) / "northwind.txt").write_text(self.quote_text)
                if self.increase_text:
                    (Path(tmp) / "northwind_increase.txt").write_text(self.increase_text)
                demo_module.QUOTES_DIR = Path(tmp)
            demo_module.POLICY = self.policy
            try:
                demo.run()
            finally:
                demo_module.QUOTES_DIR, demo_module.POLICY = EXAMPLE_QUOTES, DEFAULT_POLICY

    def state(self) -> dict:
        return {"status": self.status, "pending": self.pending, "error": self.error}


runs: dict[str, Run] = {}
db.runs.update_many(
    {"status": {"$in": ACTIVE}},
    {"$set": {"status": "interrupted", "error": "The server restarted while this purchase was in progress.", "finished_at": _now()}},
)

# Access: roles are code, each person's role is data. New sign-ins wait as "pending" until an admin lets them in.
ROLES = ["admin", "member", "pending"]
DEFAULT_ROLE = "pending"
RETIRED_ROLES: dict[str, str] = {}
RANK = {r: len(ROLES) - i for i, r in enumerate(ROLES)}
ENV = "live" if os.environ.get("CLERK_PUBLISHABLE_KEY", "").startswith("pk_live_") else "preview"
IN_ENV = {"env": {"$in": [ENV, None]}}


def effective_role(role) -> str:
    role = RETIRED_ROLES.get(role, role)
    return role if role in ROLES else DEFAULT_ROLE


def _clerk_profile(user_id: str) -> dict:
    """One Clerk lookup on first sign-in: verified admin email, plus the email and name shown on the Team page."""
    admins = {e.strip().lower() for e in os.environ.get("ADMIN_EMAIL", "").split(",") if e.strip()}
    r = requests.get(f"https://api.clerk.com/v1/users/{user_id}", timeout=10,
                     headers={"Authorization": f"Bearer {os.environ['CLERK_SECRET_KEY']}", "User-Agent": "emergent-app"})
    r.raise_for_status()
    data = r.json()
    emails = data["email_addresses"]
    primary = next((e for e in emails if e["id"] == data.get("primary_email_address_id")), emails[0] if emails else None)
    return {
        "is_admin": any(e["email_address"].lower() in admins and (e.get("verification") or {}).get("status") == "verified" for e in emails),
        "email": primary["email_address"] if primary else None,
        "name": " ".join(filter(None, [data.get("first_name"), data.get("last_name")])) or None,
    }


def current_member(user: dict = Depends(require_user)) -> dict:
    uid = user["user_id"]
    member = db.users.find_one({"user_id": uid}, {"_id": 0})
    if member is None or not member.get("role"):  # first sign-in
        profile = _clerk_profile(uid)
        role = "admin" if profile["is_admin"] else DEFAULT_ROLE
        db.users.update_one({"user_id": uid, "role": {"$in": [None, ""]}}, {"$set": {"role": role}})
        member = db.users.find_one_and_update(
            {"user_id": uid},
            {"$setOnInsert": {"user_id": uid, "role": role, "email": profile["email"], "name": profile["name"], "joined_at": _now()}},
            upsert=True, projection={"_id": 0}, return_document=ReturnDocument.AFTER)
    if member.get("env") != ENV:
        db.users.update_one({"user_id": uid}, {"$set": {"env": ENV}})
    return member | {"env": ENV, "role": effective_role(member["role"])}


def require_role(*roles: str):
    def check(member: dict = Depends(current_member)) -> dict:
        if member["role"] not in roles:
            raise HTTPException(status_code=403, detail="Not allowed")
        return member
    return check


require_access = require_role("admin", "member")

app = FastAPI()
api = APIRouter(prefix="/api")
secure = APIRouter(prefix="/api", dependencies=[Depends(require_access)])


@app.on_event("startup")
def move_retired_roles():
    for old, new in RETIRED_ROLES.items():
        db.users.update_many({"role": old}, {"$set": {"role": new}})


class StartRun(BaseModel):
    auto: bool = False
    auto_approve_max: float | None = Field(default=None, gt=0, le=1_000_000)
    reserve_floor: float | None = Field(default=None, ge=0, le=1_000_000)
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


@secure.get("/context")
def context():
    """What a purchase starts from: the vendor quote, the spending policy and the cash plan, read from leash/."""
    policy = DEFAULT_POLICY
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


@secure.get("/runs")
def list_runs():
    return [_public(doc) for doc in db.runs.find({}, {"events": 0}).sort("started_at", -1)]


@secure.post("/runs")
def start_run(body: StartRun, member: dict = Depends(require_access)):
    if any(run.status in ACTIVE for run in runs.values()):
        raise HTTPException(409, "a run is already in progress")
    policy = replace(
        DEFAULT_POLICY,
        auto_approve_max=DEFAULT_POLICY.auto_approve_max if body.auto_approve_max is None else body.auto_approve_max,
        reserve_floor=DEFAULT_POLICY.reserve_floor if body.reserve_floor is None else body.reserve_floor,
    )
    run = Run(body.auto, body.quote_text, (body.increase_text or "").strip() or None, policy, member.get("email"))
    runs[run.id] = run
    threading.Thread(target=run.execute, daemon=True).start()
    return _snapshot(run.id)


@secure.get("/runs/latest")
def latest_run():
    doc = db.runs.find_one({}, {"_id": 1}, sort=[("started_at", -1)])
    return _snapshot(doc["_id"]) if doc else None


@secure.get("/runs/{run_id}")
def get_run(run_id: str, after: int = 0):
    return _snapshot(run_id, after)


@secure.get("/runs/{run_id}/stream")
def stream_run(run_id: str, request: Request, after: int = 0):
    run = runs.get(run_id)
    if run is None:
        raise HTTPException(404, "run is not live")
    sent = int(request.headers.get("last-event-id") or after)
    return StreamingResponse(_stream(run, sent), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache, no-transform", "X-Accel-Buffering": "no"})


@secure.post("/runs/{run_id}/approval")
def decide(run_id: str, body: Decision, member: dict = Depends(require_access)):
    run = runs.get(run_id)
    if run is None:
        if db.runs.count_documents({"_id": run_id}) == 0:
            raise HTTPException(404, "run not found")
        raise HTTPException(409, "no approval is pending")
    if run.pending is None:
        raise HTTPException(409, "no approval is pending")
    if body.digest != run.pending["digest"]:
        raise HTTPException(409, "this approval is no longer the pending one")
    run.answer(body.approved, body.note, member.get("email"))
    return {"ok": True}


@secure.post("/quotes/extract")
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


@secure.get("/runs/{run_id}/export")
def export_run(run_id: str):
    snap = _snapshot(run_id)
    events = snap.pop("events")
    for key in ("pending", "total", "after", "share_token"):
        snap.pop(key)
    return JSONResponse({"purchase": snap, "exported_at": _now(), "events": events},
                        headers={"Content-Disposition": f'attachment; filename="leash-purchase-{snap["seq"]}.json"'})


@secure.post("/runs/{run_id}/share")
def share_run(run_id: str):
    snap = _snapshot(run_id)
    if snap["status"] in ACTIVE:
        raise HTTPException(409, "a purchase can be shared once it has finished")
    token = snap["share_token"] or secrets.token_urlsafe(16)
    db.runs.update_one({"_id": run_id}, {"$set": {"share_token": token}})
    return {"token": token}


@secure.delete("/runs/{run_id}/share")
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


class RoleIn(BaseModel):
    role: str


@api.get("/me")
def me(member: dict = Depends(current_member)):
    return {key: member.get(key) for key in ("user_id", "email", "name", "role")}


@api.get("/users")
def list_users(admin: dict = Depends(require_role("admin"))):
    people = list(db.users.find(IN_ENV, {"_id": 0}).sort("joined_at", 1))
    return {"roles": [r for r in ROLES if RANK[r] <= RANK[admin["role"]]],
            "users": [p | {"role": effective_role(p.get("role"))} for p in people]}


@api.patch("/users/{user_id}/role")
def set_role(user_id: str, body: RoleIn, admin: dict = Depends(require_role("admin"))):
    if body.role not in ROLES or RANK[body.role] > RANK[admin["role"]]:
        raise HTTPException(status_code=403, detail="Not allowed")
    target = db.users.find_one({"user_id": user_id, **IN_ENV}, {"_id": 0})
    if target is None:
        raise HTTPException(status_code=404, detail="Not found")
    if (effective_role(target.get("role")) == "admin" and body.role != "admin"
            and db.users.count_documents({"role": "admin", **IN_ENV}) <= 1):
        raise HTTPException(status_code=409, detail="Keep at least one admin")
    db.users.update_one({"user_id": user_id}, {"$set": {"role": body.role}})
    return {"user_id": user_id, "role": body.role}


app.include_router(api)
app.include_router(secure)
app.include_router(clerk_router)
app.add_middleware(
    CORSMiddleware,
    allow_origins=os.environ.get("CORS_ORIGINS", "*").split(","),
    allow_methods=["*"],
    allow_headers=["*"],
)
