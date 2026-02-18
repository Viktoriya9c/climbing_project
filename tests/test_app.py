import os
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def test_health():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_state():
    response = client.get("/state")
    assert response.status_code == 200
    assert "video" in response.json()


def test_upload_rejects_non_video(tmp_path):
    test_file = tmp_path / "test.txt"
    test_file.write_text("hello")

    with open(test_file, "rb") as f:
        response = client.post(
            "/upload",
            files={"file": ("test.txt", f, "text/plain")}
        )

    assert response.status_code == 400
    assert "error" in response.json()
