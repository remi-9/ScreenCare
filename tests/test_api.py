from fastapi.testclient import TestClient

from app import app

client = TestClient(app)


def test_page_renders():
    response = client.get("/")
    assert response.status_code == 200
    assert "ScreenCare" in response.text


def test_act_round_trip():
    started = client.post("/api/act", json={"action": "start", "payload": {"mode": "classic"}})
    assert started.status_code == 200
    body = started.json()
    assert body["session"]["phase"] == "focusing"
    assert body["session"]["planned_s"] == 25 * 60

    paused = client.post("/api/act", json={"action": "pause", "session": body["session"]})
    assert paused.json()["session"]["phase"] == "paused"


def test_invalid_transition_is_409():
    response = client.post("/api/act", json={"action": "extend"})
    assert response.status_code == 409
    assert "idle" in response.json()["detail"]


def test_bad_payload_is_422():
    response = client.post("/api/act", json={"action": "start", "payload": {"mode": "turbo"}})
    assert response.status_code == 422


def test_wrong_payload_type_is_422():
    response = client.post("/api/act", json={"action": "quiet", "payload": {"minutes": None}})
    assert response.status_code == 422


def test_summary():
    response = client.post("/api/summary", json={"records": [], "tz_offset_minutes": 60})
    assert response.status_code == 200
    assert len(response.json()["trend"]) == 7


def test_public_files_are_served_locally():
    files = [("/app.js", "javascript"), ("/app.css", "css"), ("/manifest.webmanifest", "manifest")]
    for path, kind in files:
        response = client.get(path)
        assert response.status_code == 200, path
        assert kind in response.headers["content-type"]


def test_public_files_cannot_escape_the_folder():
    assert client.get("/../pyproject.toml").status_code == 404
    assert client.get("/%2e%2e/pyproject.toml").status_code == 404
    assert client.get("/missing.js").status_code == 404


def test_health():
    assert client.get("/api/health").json() == {"status": "ok"}
