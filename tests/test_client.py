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
        {"databaseId": "db001", "label": "Base Test", "ownerId": 42,
         "billingAccountId": 7, "suspended": False},
        {"databaseId": "db002", "label": "Base Prod", "ownerId": 42,
         "billingAccountId": 7, "suspended": False},
    ])
    dbs = client.get_databases()
    assert len(dbs) == 2
    assert dbs[0].label == "Base Test"
    assert dbs[0].owner_id == "42"
    assert dbs[0].suspended is False
    assert isinstance(dbs[0], Database)


@patch("requests.Session.request")
def test_get_database(mock_req, client):
    mock_req.return_value = make_mock_response(200, {
        "databaseId": "db001", "label": "Ma Base",
        "resources": [
            {"id": "f1", "label": "Formulaire 1", "type": "FORM"},
        ],
    })
    db = client.get_database("db001")
    assert db.id == "db001"
    assert db.label == "Ma Base"


@patch("requests.Session.request")
def test_get_database_resources_from_tree(mock_req, client):
    # get_database_resources() ne tape pas un endpoint séparé : les
    # ressources viennent du "database tree" (même endpoint que
    # get_database()).
    mock_req.return_value = make_mock_response(200, {
        "databaseId": "db001", "label": "Ma Base",
        "resources": [
            {"id": "f1", "label": "Formulaire 1", "type": "FORM"},
            {"id": "d1", "label": "Dossier", "type": "FOLDER"},
        ],
    })
    resources = client.get_database_resources("db001")
    assert len(resources) == 2
    assert resources[0].is_form
    assert resources[1].is_folder


@patch("requests.Session.request")
def test_add_database(mock_req, client):
    mock_req.return_value = make_mock_response(200, {
        "databaseId": "db_new", "label": "Nouvelle Base"
    })
    db = client.add_database("Nouvelle Base")
    assert db.label == "Nouvelle Base"

    # Vérifie que le payload envoyé correspond au format réel de l'API
    # (id + label + templateId, confirmé par R/databases.R).
    sent = mock_req.call_args.kwargs.get("json")
    assert sent["label"] == "Nouvelle Base"
    assert sent["templateId"] == "blank"
    assert "id" in sent


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
             "required": True, "key": False,
             "typeParameters": {"barcode": False}},
            {"id": "f2", "label": "Age", "type": "quantity",
             "required": False, "key": False,
             "typeParameters": {"units": "ans", "aggregation": "SUM"}},
        ]
    })
    schema = client.get_form_schema("form001")
    assert schema.id == "form001"
    assert schema.label == "Enquête"
    assert len(schema.fields) == 2
    assert schema.fields[1].units == "ans"
    assert isinstance(schema, FormSchema)


@patch("requests.Session.request")
def test_get_form_schema_not_found(mock_req, client):
    mock_req.return_value = make_mock_response(404, {"message": "Formulaire introuvable"})
    with pytest.raises(NotFoundError):
        client.get_form_schema("form_inexistant")


@patch("activityinfo.client.generate_cuid", return_value="form_new")
@patch("requests.Session.request")
def test_add_form(mock_req, mock_cuid, client):
    # Réponse réelle attendue : {database: {...}, forms: [{id, schema}]}
    # generate_cuid() est mocké pour renvoyer un id déterministe afin
    # de pouvoir le faire correspondre à la réponse simulée ci-dessous.
    mock_req.return_value = make_mock_response(200, {
        "database": {"databaseId": "db001"},
        "forms": [
            {"id": "form_new", "schema": {
                "id": "form_new", "label": "Nouveau formulaire",
                "databaseId": "db001",
                "elements": [
                    {"id": "f1", "label": "Nom", "type": "FREE_TEXT",
                     "required": True, "key": False,
                     "typeParameters": {"barcode": False}},
                ],
            }}
        ],
    })
    schema = client.add_form(
        database_id="db001",
        label="Nouveau formulaire",
        elements=[text_field("Nom", code="NOM", required=True)],
    )
    assert schema.id == "form_new"
    assert schema.label == "Nouveau formulaire"

    # Vérifie l'enveloppe formResource/formClass envoyée
    sent = mock_req.call_args.kwargs.get("json")
    assert "formResource" in sent
    assert "formClass" in sent
    assert sent["formResource"]["type"] == "FORM"
    assert sent["formResource"]["visibility"] == "PRIVATE"


@patch("requests.Session.request")
def test_update_form_schema(mock_req, client):
    mock_req.return_value = make_mock_response(200, {
        "forms": [
            {"id": "form001", "schema": {
                "id": "form001", "label": "Mise à jour",
                "databaseId": "db001", "elements": [],
            }}
        ]
    })
    schema = FormSchema(id="form001", label="Mise à jour", database_id="db001")
    result = client.update_form_schema(schema)
    assert result.label == "Mise à jour"


@patch("requests.Session.request")
def test_delete_form(mock_req, client):
    mock_req.return_value = make_mock_response(200, {})
    # Nouvelle signature : database_id requis en plus de form_id.
    client.delete_form("db001", "form001")
    sent = mock_req.call_args.kwargs.get("json")
    assert sent["resourceDeletions"] == ["form001"]


# ─── TESTS : ENREGISTREMENTS ──────────────────────────────────────────────────

@patch("requests.Session.request")
def test_get_records_via_column_query(mock_req, client):
    # get_records() utilise désormais le mécanisme de requête colonnaire
    # (POST /resources/query/columns), pas une pagination par curseur.
    # 1er appel : get_form_schema (pour connaître les champs)
    # 2e appel : query/columns (une seule page ici, totalRows == rows)
    mock_req.side_effect = [
        make_mock_response(200, {
            "id": "form001", "label": "Test", "databaseId": "db001",
            "elements": [
                {"id": "f1", "label": "Nom", "code": "NOM", "type": "FREE_TEXT",
                 "required": False, "key": False,
                 "typeParameters": {"barcode": False}},
            ],
        }),
        make_mock_response(200, {
            "rows": 2,
            "totalRows": 2,
            "columns": [
                {"id": "_id", "storage": "array", "type": "STRING",
                 "values": ["r1", "r2"]},
                {"id": "_lastEditTime", "storage": "array", "type": "NUMBER",
                 "values": [1000, 2000]},
                {"id": "NOM", "storage": "array", "type": "STRING",
                 "values": ["Alice", "Bob"]},
            ],
        }),
    ]
    records = client.get_records("form001")
    assert len(records) == 2
    assert records[0].record_id == "r1"
    assert records[0].values["NOM"] == "Alice"
    assert isinstance(records[0], FormRecord)


@patch("requests.Session.request")
def test_add_record(mock_req, client):
    mock_req.side_effect = [
        make_mock_response(200, {}),  # POST /update
        make_mock_response(200, {     # GET /form/.../record/...
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


# ─── TESTS : MODÈLES / CHAMPS ─────────────────────────────────────────────────

def test_text_field_creation():
    f = text_field("Nom complet", code="NOM", required=True)
    assert f["label"] == "Nom complet"
    assert f["code"] == "NOM"
    assert f["required"] is True
    assert f["type"] == "FREE_TEXT"
    assert f["typeParameters"]["barcode"] is False


def test_quantity_field_creation():
    # Le vrai type API est "quantity" (minuscule), pas "QUANTITY".
    f = quantity_field("Nombre de bénéficiaires", code="NB", units="personnes")
    assert f["type"] == "quantity"
    assert f["typeParameters"]["units"] == "personnes"
    assert f["typeParameters"]["aggregation"] == "SUM"


def test_single_select_field_creation():
    # Le vrai type API est "enumerated" avec cardinality="single",
    # pas un type "SINGLE_SELECTION" séparé.
    f = single_select_field("Sexe", ["Homme", "Femme", "Autre"], code="SEXE")
    assert f["type"] == "enumerated"
    assert f["typeParameters"]["cardinality"] == "single"
    assert len(f["typeParameters"]["values"]) == 3


def test_form_schema_get_field():
    from activityinfo.models.field import Field
    schema = FormSchema(
        id="f1", label="Test", database_id="db1",
        fields=[
            Field(id="x1", label="Nom", type="FREE_TEXT", code="NOM"),
            Field(id="x2", label="Age", type="quantity", code="AGE"),
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
            Field(id="x2", label="Age", type="quantity", code="AGE"),
        ]
    )
    codes = schema.field_codes()
    assert "NOM" in codes
    assert "AGE" in codes


# ─── TESTS : JOBS ─────────────────────────────────────────────────────────────

@patch("requests.Session.request")
def test_wait_for_job_success(mock_req, client):
    # Les états réels sont en minuscules : "started" / "completed"
    # (confirmé par R/extractLong.R), pas "RUNNING" / "COMPLETED".
    mock_req.side_effect = [
        make_mock_response(200, {"state": "started", "percentComplete": 50}),
        make_mock_response(200, {"state": "completed", "result": "ok"}),
    ]
    result = client._wait_for_job("job001", poll_interval=0)
    assert result["state"] == "completed"


@patch("requests.Session.request")
def test_wait_for_job_failure(mock_req, client):
    mock_req.return_value = make_mock_response(200, {
        "state": "failed",
        "error": {"code": "IMPORT_ERROR", "message": "Erreur d'import"}
    })
    with pytest.raises(JobError):
        client._wait_for_job("job002", poll_interval=0)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
