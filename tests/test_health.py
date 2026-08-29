from fastapi.testclient import TestClient


def test_health_returns_mode_and_readiness(client: TestClient) -> None:
    response = client.get("/health")
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"
    assert payload["mode"] == "mock"
    assert payload["ready"] is True
