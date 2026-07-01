from fastapi.testclient import TestClient

import main


def test_health_endpoint_reports_core_checks():
    client = TestClient(main.app)

    response = client.get("/health")

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"
    assert payload["service"] == "face-attendance-system"
    assert payload["checks"]["api"] == "ok"
    assert payload["checks"]["face_quality_config"] == "ok"
    assert payload["checks"]["multi_frame_voting_config"] == "ok"
    assert "legacy_embeddings_enabled" in payload
