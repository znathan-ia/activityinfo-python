"""
Tests unitaires pour ActivityInfoClient.
Utilise unittest.mock pour simuler les appels API.
"""

import pytest
from unittest.mock import patch, MagicMock, PropertyMock
import json

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from activityinfo import ActivityInfoClient
from activityinfo.exceptions import (
    AuthenticationError, NotFoundError, ValidationError, JobError
)
from activityinfo.models import (
    Database, FormSchema, FormRecord,
    text_field, quantity_field, single_select_field
)


# ─── FIXTURES ─────────────────────────────────────────────────────────────────

@pytest.fixture
def client():
    return ActivityInfoClient("fake_token_for_tests")


def make_mock_response(status_code: int, data=None):
    """Crée une réponse HTTP mockée."""
    mock = MagicMock()
    mock.status_code = status_code
    mock.content = b"content" if data else b""
    mock.text = json.dumps(data) if data else ""
    mock.json.return_value = data or {}
    return mock


# ─── TESTS : INITIALISATION ───────────────────────────────────────────────────

def test_client_init_ok():
    c = ActivityInfoClient("valid_token")
    assert c is not None


def test_client_init_no_token():
    with pytest.raises(ValidationError):
        ActivityInfoClient("")


def test_client_repr():
    c = ActivityInfoClient("token")
    assert "ActivityInfoClient" in repr(c)


# ─── TESTS : BASES DE DONNÉES ─────────────────────────────────────────────────

@patch("requests.Session.request")
def test_get_databases(mock_req, client):
    mock_req.return_value = make_mock_response(200, [
        {"databaseId": "db001", "label": "Base Test"},
        {"databaseId": "db002", "label": "Base Prod"},
    ])
    dbs = client.get_databases()
    assert len(dbs) == 2
    assert dbs[0].label == "Base Test"
    assert isinstance(dbs[0], Database)


@patch("requests.Session.request")
def test_get_database(mock_req, client):
    mock_req.return_value = make_mock_response(200, {
        "databaseId": "db001", "label": "Ma Base"
    })
    db = client.get_database("db001")
    assert db.id == "db001"
    assert db.label == "Ma Base"


@patch("requests.Session.request")
def test_add_database(mock_req, client):
    mock_req.return_value = make_mock_response(200, {
        "databaseId": "db_new", "label": "Nouvelle Base"
    })
    db = client.add_database("Nouvelle Base", description="Test")
    assert db.label == "Nouvelle Base"


# ─── TESTS : FORMULAIRES ──────────────────────────────────────────────────────

@patch("requests.Session.request")
def test_get_form_schema(mock_req, client):
    mock_req.return_value = make_mock_response(200, {
        "id": "form001",
        "label": "Enquête",
        "databaseId": "db001",
        "schemaVersion": 5,
        "elements": [
            {"id": "f1", "label": "Nom", "type": "FREE_TEXT",
             "required": True, "key": False},
            {"id": "f2", "label": "Age", "type": "QUANTITY",
             "required": False, "key": False},
        ]
    })
    schema = client.get_form_schema("form001")
    assert schema.id == "form001"
    assert schema.label == "Enquête"
    assert len(schema.fields) == 2
    assert isinstance(schema, FormSchema)


@patch("requests.Session.request")
def test_get_form_schema_not_found(mock_req, client):
    mock_req.return_value = make_mock_response(404, {"message": "Formulaire introuvable"})
    with pytest.raises(NotFoundError):
        client.get_form_schema("form_inexistant")


# ─── TESTS : ENREGISTREMENTS ──────────────────────────────────────────────────

@patch("requests.Session.request")
def test_get_records_paginated(mock_req, client):
    # Simule 2 pages
    mock_req.side_effect = [
        make_mock_response(200, {
            "items": [
                {"recordId": "r1", "fields": {"NOM": "Alice"}},
                {"recordId": "r2", "fields": {"NOM": "Bob"}},
            ],
            "cursor": "cursor_page_2"
        }),
        make_mock_response(200, {
            "items": [
                {"recordId": "r3", "fields": {"NOM": "Charlie"}},
            ],
            "cursor": None
        }),
    ]
    records = client.get_records("form001")
    assert len(records) == 3
    assert records[0].record_id == "r1"
    assert isinstance(records[0], FormRecord)


@patch("requests.Session.request")
def test_add_record(mock_req, client):
    mock_req.side_effect = [
        make_mock_response(200, {}),  # POST /api/update
        make_mock_response(200, {     # GET /api/form/.../record/...
            "recordId": "new_rec", "fields": {"NOM": "Alice"}
        }),
    ]
    record = client.add_record("form001", {"NOM": "Alice", "AGE": 30})
    assert record.record_id == "new_rec"


@patch("requests.Session.request")
def test_delete_record(mock_req, client):
    mock_req.return_value = make_mock_response(200, {})
    # Ne doit pas lever d'exception
    client.delete_record("form001", "rec001")
    assert mock_req.called


# ─── TESTS : GESTION ERREURS ──────────────────────────────────────────────────

@patch("requests.Session.request")
def test_authentication_error(mock_req, client):
    mock_req.return_value = make_mock_response(401, {"message": "Unauthorized"})
    with pytest.raises(AuthenticationError):
        client.get_databases()


@patch("requests.Session.request")
def test_rate_limit_error(mock_req, client):
    from activityinfo.exceptions import RateLimitError
    mock_req.return_value = make_mock_response(429, {"message": "Too Many Requests"})
    with pytest.raises(RateLimitError):
        client.get_databases()


# ─── TESTS : MODÈLES ──────────────────────────────────────────────────────────

def test_text_field_creation():
    f = text_field("Nom complet", code="NOM", required=True)
    assert f["label"] == "Nom complet"
    assert f["code"] == "NOM"
    assert f["required"] is True
    assert f["type"] == "FREE_TEXT"


def test_quantity_field_creation():
    f = quantity_field("Nombre de bénéficiaires", code="NB", units="personnes")
    assert f["type"] == "QUANTITY"
    assert f["typeParameters"]["units"] == "personnes"


def test_single_select_field_creation():
    f = single_select_field("Sexe", ["Homme", "Femme", "Autre"], code="SEXE")
    assert f["type"] == "SINGLE_SELECTION"
    assert len(f["typeParameters"]["values"]) == 3


def test_form_schema_get_field():
    from activityinfo.models.field import Field
    schema = FormSchema(
        id="f1", label="Test", database_id="db1",
        fields=[
            Field(id="x1", label="Nom", type="FREE_TEXT", code="NOM"),
            Field(id="x2", label="Age", type="QUANTITY", code="AGE"),
        ]
    )
    f = schema.get_field("NOM")
    assert f is not None
    assert f.code == "NOM"


def test_form_schema_field_codes():
    from activityinfo.models.field import Field
    schema = FormSchema(
        id="f1", label="Test", database_id="db1",
        fields=[
            Field(id="x1", label="Nom", type="FREE_TEXT", code="NOM"),
            Field(id="x2", label="Age", type="QUANTITY", code="AGE"),
        ]
    )
    codes = schema.field_codes()
    assert "NOM" in codes
    assert "AGE" in codes


# ─── TESTS : JOBS ─────────────────────────────────────────────────────────────

@patch("requests.Session.request")
def test_wait_for_job_success(mock_req, client):
    mock_req.side_effect = [
        make_mock_response(200, {"state": "RUNNING"}),
        make_mock_response(200, {"state": "COMPLETED", "result": "ok"}),
    ]
    result = client._wait_for_job("job001", poll_interval=0)
    assert result["state"] == "COMPLETED"


@patch("requests.Session.request")
def test_wait_for_job_failure(mock_req, client):
    mock_req.return_value = make_mock_response(200, {
        "state": "FAILED",
        "error": {"message": "Erreur d'import"}
    })
    with pytest.raises(JobError):
        client._wait_for_job("job002", poll_interval=0)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
