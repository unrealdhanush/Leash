# Leash web API tests (non-run-starting endpoints; run-starting flows are tested via UI to limit sandbox usage)
import os
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL").rstrip("/")


@pytest.fixture
def s():
    return requests.Session()


# Health
def test_health(s):
    r = s.get(f"{BASE_URL}/api/health")
    assert r.status_code == 200
    d = r.json()
    assert d["ok"] is True
    assert d["airwallex_configured"] is True
    assert d["cardholder_configured"] is True
    assert isinstance(d["model"], str) and d["model"]


# Latest run snapshot shape
def test_latest_shape(s):
    r = s.get(f"{BASE_URL}/api/runs/latest")
    assert r.status_code == 200
    d = r.json()
    if d is None:
        pytest.skip("no runs yet")
    for k in ("id", "auto", "status", "pending", "total", "after", "events"):
        assert k in d
    assert d["total"] == len(d["events"])


# Pagination with after=n
def test_get_run_after(s):
    d = s.get(f"{BASE_URL}/api/runs/latest").json()
    if not d:
        pytest.skip("no runs yet")
    r = s.get(f"{BASE_URL}/api/runs/{d['id']}", params={"after": 5})
    assert r.status_code == 200
    p = r.json()
    assert p["after"] == 5
    assert p["events"] == d["events"][5:]


# Unknown run
def test_unknown_run_404(s):
    assert s.get(f"{BASE_URL}/api/runs/doesnotexist").status_code == 404
    assert s.post(f"{BASE_URL}/api/runs/doesnotexist/approval", json={"approved": True}).status_code == 404


# Approval with nothing pending
def test_approval_no_pending_409(s):
    d = s.get(f"{BASE_URL}/api/runs/latest").json()
    if not d or d["status"] == "waiting_approval":
        pytest.skip("not applicable")
    r = s.post(f"{BASE_URL}/api/runs/{d['id']}/approval", json={"approved": True})
    assert r.status_code == 409
    assert "pending" in r.json()["detail"]


# Validation
def test_approval_validation_422(s):
    d = s.get(f"{BASE_URL}/api/runs/latest").json()
    if not d:
        pytest.skip("no runs yet")
    r = s.post(f"{BASE_URL}/api/runs/{d['id']}/approval", json={})
    assert r.status_code == 422
