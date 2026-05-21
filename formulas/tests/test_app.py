from fastapi.testclient import TestClient
from formulas_api.main import app

client = TestClient(app)

def test_health():
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json().get("render_available") is True

def test_extract_no_pdf():
    r = client.post("/extract", files={"file": ("a.txt", b"hi", "text/plain")})
    assert r.status_code in (400, 415)

def test_render_valid():
    r = client.post("/render", json={"latex": "E=mc^2"})
    assert r.status_code == 200
    assert r.headers["content-type"] == "image/png"

def test_render_empty():
    r = client.post("/render", json={"latex": ""})
    assert r.status_code == 400

def test_render_too_long():
    r = client.post("/render", json={"latex": "x" * 600})
    assert r.status_code == 400