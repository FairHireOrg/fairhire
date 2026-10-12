from __future__ import annotations

import io
import json

from fastapi.testclient import TestClient

import api

client = TestClient(api.app)
SAMPLE = """Morgan Rivera
morgan.rivera@example.com | 415-555-0132 | San Francisco, CA

Experience
Backend Engineer | Harbor Software | June 2022 – Present
- Built Python services that reduced processing time by 32%.
- Designed REST APIs for a customer reporting platform.

Education
B.S. Computer Science | River Valley University | May 2019

Skills
Languages: Python, SQL, Go
"""


def test_import_score_export_cycle():
    r = client.post("/api/resume/import", data={"resume_text": SAMPLE})
    assert r.status_code == 200
    body = r.json()
    assert body["document"]["contact"]["email"] == "morgan.rivera@example.com"
    assert body["ats"]["recommendations"] is not None

    doc = body["document"]
    again = client.post("/api/resume/score", json={"document": doc}).json()
    assert again["ats"] == body["ats"]            # deterministic
    assert again["text"] == body["text"]

    docx = client.post("/api/resume/export", json={"document": doc, "format": "docx"})
    assert docx.status_code == 200 and docx.content[:2] == b"PK"
    txt = client.post("/api/resume/export", json={"document": doc, "format": "txt"})
    assert "Backend Engineer" in txt.text


def test_exported_docx_reimports_to_same_document():
    """What we hand a user must parse back into what they edited."""
    body = client.post("/api/resume/import", data={"resume_text": SAMPLE}).json()
    docx = client.post("/api/resume/export", json={"document": body["document"], "format": "docx"}).content
    back = client.post("/api/resume/import", files={"resume": ("r.docx", io.BytesIO(docx))}).json()

    def strip(d):
        if isinstance(d, dict):
            return {k: strip(v) for k, v in d.items() if k not in ("id", "title")}
        if isinstance(d, list):
            return [strip(v) for v in d]
        return d

    assert json.dumps(strip(back["document"]), sort_keys=True) == json.dumps(strip(body["document"]), sort_keys=True)


def test_errors_are_plain():
    assert client.post("/api/resume/import").status_code == 400
    r = client.post("/api/resume/import", files={"resume": ("x.exe", io.BytesIO(b"abc"))})
    assert r.status_code == 400 and "Unsupported" in r.json()["detail"]
