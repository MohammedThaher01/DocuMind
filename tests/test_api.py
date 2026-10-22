"""API-level tests: the synchronous endpoint, the new status fields and the
existing DOCX download behaviour.

The graph runs for real here, but ``main.call_llm`` is replaced by
``support.FakeLLM``, so no API key is needed and nothing is nondeterministic.
"""
import os

import pytest
from fastapi.testclient import TestClient
from docx import Document

import main

from support import critique, issue, plan_with


@pytest.fixture
def client():
    return TestClient(main.app)


def test_health_endpoint(client):
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


def test_blank_request_is_rejected(client):
    assert client.post("/agent", json={"request": "   "}).status_code == 422
    assert client.post("/agent", json={}).status_code == 422


def test_sync_agent_endpoint_returns_the_new_status_fields(client, fake_llm, isolated_output_dir):
    fake_llm(plan=plan_with(["Summary"]), critiques=[critique()])

    resp = client.post("/agent", json={"request": "Write a short business report."})
    assert resp.status_code == 200, resp.text

    body = resp.json()
    assert body["status"] == main.STATUS_VALIDATED
    assert body["review_required"] is False
    assert body["revision_count"] == 0
    assert body["unresolved_issues"] == []
    assert body["download_url"].startswith("/download/")
    assert "passed self-validation" in body["message"]


def test_generated_document_can_be_downloaded(client, fake_llm, isolated_output_dir):
    fake_llm(plan=plan_with(["Summary"]), critiques=[critique()])
    body = client.post("/agent", json={"request": "Write a short business report."}).json()

    resp = client.get(body["download_url"])
    assert resp.status_code == 200
    assert resp.headers["content-type"] == (
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    )
    assert len(resp.content) > 0

    # The bytes really are a .docx, not just a file with the right extension.
    path = os.path.join(main.OUTPUT_DIR, os.path.basename(body["download_url"]))
    doc = Document(path)
    assert any(p.text == "Agent Execution Log" for p in doc.paragraphs)


def test_missing_download_returns_404(client):
    assert client.get("/download/does_not_exist.docx").status_code == 404


def test_api_reports_review_required_instead_of_a_validation_pass(client, fake_llm, isolated_output_dir):
    bad = critique([issue("critical", "unsupported_specifics", "Invented a 10% discount")])
    fake_llm(plan=plan_with(["Summary"]), critiques=[bad, bad])

    body = client.post("/agent", json={"request": "Write a short business report."}).json()

    assert body["status"] == main.STATUS_REVIEW_REQUIRED
    assert body["review_required"] is True
    assert body["revision_count"] == 1
    assert body["unresolved_issues"]
    assert "NOT validated" in body["message"]
    # The document is still produced so the user can act on it.
    assert client.get(body["download_url"]).status_code == 200


def test_no_streaming_or_job_routes_exist():
    """The API is synchronous: no SSE/polling endpoints should be present."""
    paths = {getattr(r, "path", "") for r in main.app.routes}
    assert not any("stream" in p for p in paths)
    assert "/agent" in paths
    assert "/agent/sync" not in paths
