# Leash web API tests. Covers the endpoints added in this iteration too:
# POST /api/quotes/extract, GET /api/runs/{id}/export, POST/DELETE /api/runs/{id}/share, GET /api/shared/{token}.
import io
import os
import pytest
import requests

from reportlab.pdfgen import canvas

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL").rstrip("/")


@pytest.fixture
def s():
    return requests.Session()


@pytest.fixture
def finished_run_id(s):
    for row in s.get(f"{BASE_URL}/api/runs").json():
        if row["status"] not in ("running", "waiting_approval"):
            return row["id"]
    pytest.skip("no finished run available")


# ---------------- Health ----------------
def test_health(s):
    r = s.get(f"{BASE_URL}/api/health")
    assert r.status_code == 200
    d = r.json()
    assert d["ok"] is True
    assert d["airwallex_configured"] is True
    assert d["cardholder_configured"] is True


# ---------------- Runs list shape ----------------
def test_runs_list_shape(s):
    r = s.get(f"{BASE_URL}/api/runs")
    assert r.status_code == 200
    arr = r.json()
    assert isinstance(arr, list)
    if not arr:
        pytest.skip("no runs yet")
    row = arr[0]
    for k in ("id", "seq", "auto", "started_at", "finished_at", "status", "model", "summary", "quote_source", "share_token"):
        assert k in row, f"missing {k}"
    assert "events" not in row
    assert "_id" not in row


# ---------------- Unknown run ----------------
def test_unknown_run_404(s):
    assert s.get(f"{BASE_URL}/api/runs/doesnotexist").status_code == 404
    r = s.post(f"{BASE_URL}/api/runs/doesnotexist/approval", json={"approved": True, "digest": "x"})
    assert r.status_code == 404


# ---------------- Validation on POST /api/runs ----------------
def test_start_run_quote_text_too_short_422(s):
    r = s.post(f"{BASE_URL}/api/runs", json={"auto": True, "quote_text": "too short"})
    assert r.status_code == 422


# ---------------- Approval validation ----------------
def test_approval_validation_422(s):
    d = s.get(f"{BASE_URL}/api/runs/latest").json()
    if not d:
        pytest.skip("no runs yet")
    r = s.post(f"{BASE_URL}/api/runs/{d['id']}/approval", json={})
    assert r.status_code == 422
    r = s.post(f"{BASE_URL}/api/runs/{d['id']}/approval", json={"approved": True})
    assert r.status_code == 422


# ---------------- quotes/extract ----------------
def test_extract_txt(s):
    files = {"file": ("quote.txt", b"Hello world, this is a plain-text quote.", "text/plain")}
    r = s.post(f"{BASE_URL}/api/quotes/extract", files=files)
    assert r.status_code == 200
    d = r.json()
    assert "Hello world" in d["text"]
    assert d["filename"] == "quote.txt"


def test_extract_too_large_413(s):
    big = b"a" * (2 * 1024 * 1024 + 10)
    files = {"file": ("big.txt", big, "text/plain")}
    r = s.post(f"{BASE_URL}/api/quotes/extract", files=files)
    assert r.status_code == 413


def test_extract_binary_422(s):
    png = b"\x89PNG\r\n\x1a\n" + b"\x00\x01\x02\x03" * 50
    files = {"file": ("x.png", png, "image/png")}
    r = s.post(f"{BASE_URL}/api/quotes/extract", files=files)
    assert r.status_code == 422


def test_extract_pdf_with_text(s):
    buf = io.BytesIO()
    c = canvas.Canvas(buf)
    c.drawString(72, 720, "PDF quote: Monthly 900 USD, Annual 9900 USD.")
    c.save()
    files = {"file": ("q.pdf", buf.getvalue(), "application/pdf")}
    r = s.post(f"{BASE_URL}/api/quotes/extract", files=files)
    assert r.status_code == 200
    assert "900" in r.json()["text"]


def test_extract_pdf_no_text_422(s):
    buf = io.BytesIO()
    c = canvas.Canvas(buf)
    c.showPage()
    c.save()
    files = {"file": ("blank.pdf", buf.getvalue(), "application/pdf")}
    r = s.post(f"{BASE_URL}/api/quotes/extract", files=files)
    assert r.status_code == 422


# ---------------- share / unshare / shared ----------------
def test_share_idempotent_and_unshare(s, finished_run_id):
    r1 = s.post(f"{BASE_URL}/api/runs/{finished_run_id}/share")
    assert r1.status_code == 200
    t1 = r1.json()["token"]
    assert isinstance(t1, str) and len(t1) > 10

    r2 = s.post(f"{BASE_URL}/api/runs/{finished_run_id}/share")
    assert r2.status_code == 200
    assert r2.json()["token"] == t1, "share should be idempotent while on"

    rg = s.get(f"{BASE_URL}/api/shared/{t1}")
    assert rg.status_code == 200
    body = rg.json()
    assert body["id"] == finished_run_id
    assert "_id" not in body

    ru = s.delete(f"{BASE_URL}/api/runs/{finished_run_id}/share")
    assert ru.status_code == 200

    rg2 = s.get(f"{BASE_URL}/api/shared/{t1}")
    assert rg2.status_code == 404

    r3 = s.post(f"{BASE_URL}/api/runs/{finished_run_id}/share")
    assert r3.status_code == 200
    assert r3.json()["token"] != t1
    s.delete(f"{BASE_URL}/api/runs/{finished_run_id}/share")


def test_shared_bad_token_404(s):
    assert s.get(f"{BASE_URL}/api/shared/nope-nope-nope").status_code == 404


# ---------------- export ----------------
def test_export_shape_and_headers(s, finished_run_id):
    r = s.get(f"{BASE_URL}/api/runs/{finished_run_id}/export")
    assert r.status_code == 200
    cd = r.headers.get("Content-Disposition", "")
    assert "attachment" in cd
    assert "leash-purchase-" in cd and ".json" in cd
    d = r.json()
    assert set(["purchase", "exported_at", "events"]).issubset(d.keys())
    assert "share_token" not in d["purchase"]
    assert "_id" not in d["purchase"]
    assert d["purchase"]["id"] == finished_run_id
    assert isinstance(d["events"], list)
