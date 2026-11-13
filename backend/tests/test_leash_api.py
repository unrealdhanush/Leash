# Leash web API tests. Non-run-starting endpoints only: live run flows are covered via the UI test to limit sandbox usage.
import os
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL").rstrip("/")


@pytest.fixture
def s():
    return requests.Session()


# ---------------- Health ----------------
def test_health(s):
    r = s.get(f"{BASE_URL}/api/health")
    assert r.status_code == 200
    d = r.json()
    assert d["ok"] is True
    assert d["airwallex_configured"] is True
    assert d["cardholder_configured"] is True
    assert isinstance(d["model"], str) and d["model"]


# ---------------- Context ----------------
def test_context_shape(s):
    r = s.get(f"{BASE_URL}/api/context")
    assert r.status_code == 200
    d = r.json()
    for k in ("quote_text", "policy", "operating_cash", "cash_plan", "approver", "auto_answers"):
        assert k in d, f"missing {k}"
    assert d["policy"]["auto_approve_max"] == 5000
    assert d["policy"]["reserve_floor"] == 25000
    assert d["policy"]["horizon_weeks"] == 12
    assert isinstance(d["cash_plan"], list) and d["cash_plan"]
    assert isinstance(d["auto_answers"], list)


# ---------------- Runs list shape ----------------
def test_runs_list_shape(s):
    r = s.get(f"{BASE_URL}/api/runs")
    assert r.status_code == 200
    arr = r.json()
    assert isinstance(arr, list)
    if not arr:
        pytest.skip("no runs yet")
    row = arr[0]
    for k in ("id", "seq", "auto", "started_at", "finished_at", "status", "model", "summary"):
        assert k in row, f"missing {k}"
    assert "events" not in row
    assert "_id" not in row
    for k in ("vendor", "chosen", "plan", "card_id", "card_status", "rows", "unexpected", "approvals", "scene"):
        assert k in row["summary"], f"summary missing {k}"


# ---------------- Latest snapshot ----------------
def test_latest_shape(s):
    r = s.get(f"{BASE_URL}/api/runs/latest")
    assert r.status_code == 200
    d = r.json()
    if d is None:
        pytest.skip("no runs yet")
    for k in ("id", "auto", "status", "pending", "total", "after", "events"):
        assert k in d
    assert d["total"] == len(d["events"])


# ---------------- Pagination ----------------
def test_get_run_after(s):
    d = s.get(f"{BASE_URL}/api/runs/latest").json()
    if not d:
        pytest.skip("no runs yet")
    r = s.get(f"{BASE_URL}/api/runs/{d['id']}", params={"after": 5})
    assert r.status_code == 200
    p = r.json()
    assert p["after"] == 5
    assert p["events"] == d["events"][5:]


# ---------------- Unknown run ----------------
def test_unknown_run_404(s):
    assert s.get(f"{BASE_URL}/api/runs/doesnotexist").status_code == 404
    r = s.post(f"{BASE_URL}/api/runs/doesnotexist/approval", json={"approved": True, "digest": "x"})
    assert r.status_code == 404


# ---------------- Stream for a non-live run 404 ----------------
def test_stream_non_live_404(s):
    d = s.get(f"{BASE_URL}/api/runs/latest").json()
    if not d:
        pytest.skip("no runs yet")
    if d["status"] in ("running", "waiting_approval"):
        pytest.skip("latest is live")
    r = s.get(f"{BASE_URL}/api/runs/{d['id']}/stream")
    assert r.status_code == 404


# ---------------- Approval with nothing pending ----------------
def test_approval_no_pending_409(s):
    d = s.get(f"{BASE_URL}/api/runs/latest").json()
    if not d or d["status"] == "waiting_approval":
        pytest.skip("not applicable")
    r = s.post(f"{BASE_URL}/api/runs/{d['id']}/approval", json={"approved": True, "digest": "abc"})
    assert r.status_code == 409
    assert "pending" in r.json()["detail"]


# ---------------- Validation ----------------
def test_approval_validation_422(s):
    d = s.get(f"{BASE_URL}/api/runs/latest").json()
    if not d:
        pytest.skip("no runs yet")
    r = s.post(f"{BASE_URL}/api/runs/{d['id']}/approval", json={})
    assert r.status_code == 422
    # missing digest only is also 422
    r = s.post(f"{BASE_URL}/api/runs/{d['id']}/approval", json={"approved": True})
    assert r.status_code == 422
