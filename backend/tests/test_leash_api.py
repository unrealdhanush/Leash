"""Leash web API tests - updated for the sign-in iteration.
Covers access control (anon/pending/member/admin), role management, and the earlier endpoints
(quotes/extract, export, share/shared) that now require a member token.
"""
import io
import os
import subprocess
import pytest
import requests

from reportlab.pdfgen import canvas

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL").rstrip("/")


def _token(role):
    out = subprocess.run(
        ["python", "/app/memory/clerk_test_users.py", "token", role],
        capture_output=True, text=True, check=True,
    )
    return out.stdout.strip().splitlines()[-1]


@pytest.fixture(scope="session")
def admin_token():
    return _token("admin")


@pytest.fixture(scope="session")
def member_token():
    return _token("member")


@pytest.fixture(scope="session")
def pending_token():
    return _token("pending")


@pytest.fixture
def anon():
    return requests.Session()


@pytest.fixture
def admin(admin_token):
    s = requests.Session()
    s.headers.update({"Authorization": f"Bearer {admin_token}"})
    return s


@pytest.fixture
def member(member_token):
    s = requests.Session()
    s.headers.update({"Authorization": f"Bearer {member_token}"})
    return s


@pytest.fixture
def pending(pending_token):
    s = requests.Session()
    s.headers.update({"Authorization": f"Bearer {pending_token}"})
    return s


@pytest.fixture
def finished_run_id(member):
    r = member.get(f"{BASE_URL}/api/runs")
    assert r.status_code == 200, r.text
    for row in r.json():
        if row["status"] not in ("running", "waiting_approval"):
            return row["id"]
    pytest.skip("no finished run available")


# ---------------- Public endpoints ----------------
def test_health_public(anon):
    r = anon.get(f"{BASE_URL}/api/health")
    assert r.status_code == 200
    d = r.json()
    assert d["ok"] is True
    assert d["airwallex_configured"] is True


def test_clerk_config_public(anon):
    r = anon.get(f"{BASE_URL}/api/clerk/config")
    assert r.status_code == 200
    assert "publishable_key" in r.json() or "clerk" in r.text.lower() or r.json()


def test_shared_bad_token_public_404(anon):
    r = anon.get(f"{BASE_URL}/api/shared/nope-nope-nope")
    assert r.status_code == 404


# ---------------- Access control: anonymous -> 401 ----------------
@pytest.mark.parametrize("method,path", [
    ("GET", "/api/runs"),
    ("GET", "/api/context"),
    ("GET", "/api/runs/latest"),
    ("GET", "/api/runs/anything"),
    ("GET", "/api/runs/anything/stream"),
    ("GET", "/api/runs/anything/export"),
    ("GET", "/api/me"),
    ("GET", "/api/users"),
    ("POST", "/api/runs"),
    ("POST", "/api/quotes/extract"),
    ("POST", "/api/runs/anything/share"),
    ("POST", "/api/runs/anything/approval"),
])
def test_anon_requires_401(anon, method, path):
    r = anon.request(method, f"{BASE_URL}{path}")
    assert r.status_code == 401, f"{method} {path} => {r.status_code}"


# ---------------- Access control: pending -> 403 (except /api/me) ----------------
def test_pending_me_ok(pending):
    r = pending.get(f"{BASE_URL}/api/me")
    assert r.status_code == 200
    assert r.json()["role"] == "pending"


@pytest.mark.parametrize("path", ["/api/runs", "/api/context", "/api/runs/latest", "/api/users"])
def test_pending_forbidden(pending, path):
    r = pending.get(f"{BASE_URL}{path}")
    assert r.status_code == 403


def test_pending_start_run_forbidden(pending):
    r = pending.post(f"{BASE_URL}/api/runs", json={"auto": True})
    assert r.status_code == 403


# ---------------- Member: purchases OK, users forbidden ----------------
def test_member_me(member):
    r = member.get(f"{BASE_URL}/api/me")
    assert r.status_code == 200
    assert r.json()["role"] == "member"


def test_member_runs_ok(member):
    r = member.get(f"{BASE_URL}/api/runs")
    assert r.status_code == 200
    assert isinstance(r.json(), list)


def test_member_context_ok(member):
    r = member.get(f"{BASE_URL}/api/context")
    assert r.status_code == 200
    d = r.json()
    assert "policy" in d and "quote_text" in d


def test_member_users_forbidden(member):
    r = member.get(f"{BASE_URL}/api/users")
    assert r.status_code == 403


def test_member_patch_role_forbidden(member):
    r = member.patch(f"{BASE_URL}/api/users/any-id/role", json={"role": "member"})
    assert r.status_code == 403


# ---------------- Admin: users management ----------------
def test_admin_list_users(admin):
    r = admin.get(f"{BASE_URL}/api/users")
    assert r.status_code == 200
    d = r.json()
    assert d["roles"] == ["admin", "member", "pending"]
    assert isinstance(d["users"], list) and len(d["users"]) >= 3
    emails = [u.get("email") for u in d["users"]]
    assert any("leash.admin" in (e or "") for e in emails)
    assert any("leash.member" in (e or "") for e in emails)
    assert any("leash.pending" in (e or "") for e in emails)


def test_admin_patch_role_unknown_role_rejected(admin):
    users = admin.get(f"{BASE_URL}/api/users").json()["users"]
    target = next(u for u in users if u.get("role") == "pending")
    original = target["role"]
    r = admin.patch(f"{BASE_URL}/api/users/{target['user_id']}/role", json={"role": "superuser"})
    assert r.status_code == 403
    # ensure nothing changed
    after = admin.get(f"{BASE_URL}/api/users").json()["users"]
    assert next(u for u in after if u["user_id"] == target["user_id"])["role"] == original


def test_admin_patch_role_roundtrip_pending(admin):
    """Promote pending->member then set back. Verifies persistence via GET."""
    users = admin.get(f"{BASE_URL}/api/users").json()["users"]
    target = next(u for u in users if u.get("role") == "pending")
    uid = target["user_id"]
    try:
        r = admin.patch(f"{BASE_URL}/api/users/{uid}/role", json={"role": "member"})
        assert r.status_code == 200
        assert r.json()["role"] == "member"
        users2 = admin.get(f"{BASE_URL}/api/users").json()["users"]
        assert next(u for u in users2 if u["user_id"] == uid)["role"] == "member"
    finally:
        r = admin.patch(f"{BASE_URL}/api/users/{uid}/role", json={"role": "pending"})
        assert r.status_code == 200
        users3 = admin.get(f"{BASE_URL}/api/users").json()["users"]
        assert next(u for u in users3 if u["user_id"] == uid)["role"] == "pending"


def test_admin_cannot_demote_only_admin(admin):
    """Guard: if the test admin is the only admin, demoting must 409 and keep admin as admin."""
    users = admin.get(f"{BASE_URL}/api/users").json()["users"]
    admins = [u for u in users if u["role"] == "admin"]
    if len(admins) != 1:
        pytest.skip(f"not the single-admin case (admins={len(admins)})")
    uid = admins[0]["user_id"]
    r = admin.patch(f"{BASE_URL}/api/users/{uid}/role", json={"role": "member"})
    assert r.status_code == 409
    # confirm still admin
    users2 = admin.get(f"{BASE_URL}/api/users").json()["users"]
    assert next(u for u in users2 if u["user_id"] == uid)["role"] == "admin"


# ---------------- Legacy/data-shape tests (member token) ----------------
def test_runs_list_shape(member):
    r = member.get(f"{BASE_URL}/api/runs")
    assert r.status_code == 200
    arr = r.json()
    if not arr:
        pytest.skip("no runs yet")
    row = arr[0]
    for k in ("id", "seq", "auto", "started_at", "finished_at", "status", "model", "summary",
              "quote_source", "share_token", "policy", "started_by"):
        assert k in row, f"missing {k}"
    assert "events" not in row
    assert "_id" not in row


def test_unknown_run_404(member):
    assert member.get(f"{BASE_URL}/api/runs/doesnotexist").status_code == 404
    r = member.post(f"{BASE_URL}/api/runs/doesnotexist/approval", json={"approved": True, "digest": "x"})
    assert r.status_code == 404


def test_start_run_quote_text_too_short_422(member):
    r = member.post(f"{BASE_URL}/api/runs", json={"auto": True, "quote_text": "too short"})
    assert r.status_code == 422


def test_policy_limit_zero_422(member):
    r = member.post(f"{BASE_URL}/api/runs", json={"auto": True, "auto_approve_max": 0})
    assert r.status_code == 422


def test_policy_reserve_negative_422(member):
    r = member.post(f"{BASE_URL}/api/runs", json={"auto": True, "reserve_floor": -1})
    assert r.status_code == 422


def test_approval_validation_422(member):
    d = member.get(f"{BASE_URL}/api/runs/latest").json()
    if not d:
        pytest.skip("no runs yet")
    r = member.post(f"{BASE_URL}/api/runs/{d['id']}/approval", json={})
    assert r.status_code == 422


def test_extract_txt(member):
    files = {"file": ("quote.txt", b"Hello world, this is a plain-text quote.", "text/plain")}
    r = member.post(f"{BASE_URL}/api/quotes/extract", files=files)
    assert r.status_code == 200
    d = r.json()
    assert "Hello world" in d["text"]
    assert d["filename"] == "quote.txt"


def test_extract_too_large_413(member):
    big = b"a" * (2 * 1024 * 1024 + 10)
    r = member.post(f"{BASE_URL}/api/quotes/extract", files={"file": ("big.txt", big, "text/plain")})
    assert r.status_code == 413


def test_extract_pdf_with_text(member):
    buf = io.BytesIO()
    c = canvas.Canvas(buf)
    c.drawString(72, 720, "PDF quote: Monthly 900 USD, Annual 9900 USD.")
    c.save()
    r = member.post(f"{BASE_URL}/api/quotes/extract",
                    files={"file": ("q.pdf", buf.getvalue(), "application/pdf")})
    assert r.status_code == 200
    assert "900" in r.json()["text"]


def test_share_idempotent_and_unshare(member, anon, finished_run_id):
    r1 = member.post(f"{BASE_URL}/api/runs/{finished_run_id}/share")
    assert r1.status_code == 200
    t1 = r1.json()["token"]
    r2 = member.post(f"{BASE_URL}/api/runs/{finished_run_id}/share")
    assert r2.json()["token"] == t1

    # shared endpoint is public
    rg = anon.get(f"{BASE_URL}/api/shared/{t1}")
    assert rg.status_code == 200
    assert rg.json()["id"] == finished_run_id

    ru = member.delete(f"{BASE_URL}/api/runs/{finished_run_id}/share")
    assert ru.status_code == 200
    assert anon.get(f"{BASE_URL}/api/shared/{t1}").status_code == 404


def test_export_shape_and_headers(member, finished_run_id):
    r = member.get(f"{BASE_URL}/api/runs/{finished_run_id}/export")
    assert r.status_code == 200
    cd = r.headers.get("Content-Disposition", "")
    assert "attachment" in cd and "leash-purchase-" in cd and ".json" in cd
    d = r.json()
    assert set(["purchase", "exported_at", "events"]).issubset(d.keys())
    assert "share_token" not in d["purchase"]
    assert d["purchase"]["id"] == finished_run_id
