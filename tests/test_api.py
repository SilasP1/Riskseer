from __future__ import annotations

from fastapi.testclient import TestClient

import api


def test_normalized_case_does_not_expose_report_row_by_default(monkeypatch):
    monkeypatch.delenv("RISKSEER_API_DEBUG", raising=False)
    normalized = api.normalize_case(
        {"case_id": "1", "evaluation": {"decision_state": "SAFE_TO_PROCEED"}},
        {"private_debug_column": "value"},
    )
    assert "report_row" not in normalized


def test_investigator_endpoint_is_explicit_when_key_is_missing(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.setattr(
        api,
        "load_cases",
        lambda: [{"case_id": "1", "decision_state": "SAFE_TO_PROCEED"}],
    )
    response = TestClient(api.app).post("/api/cases/1/investigate")
    assert response.status_code == 503
    assert "OPENAI_API_KEY" in response.json()["detail"]
