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
    text_field, quantity_field, single_select_field, multi_select_field,
)
from activityinfo.models.field import Field


# ─── FIXTURES ─────────────────────────────────────────────────────────────────

@pytest.fixture
def client():
    return ActivityInfoClient("fake_token_for_tests")


def make_mock_response(status_code: int, data=None, headers=None):
    """Crée une réponse HTTP mockée."""
    mock = MagicMock()
    mock.status_code = status_code
    mock.content = b"content" if data else b""
    mock.text = json.dumps(data) if data else ""
    mock.json.return_value = data or {}
    # Content-Type par défaut JSON, pour éviter que raise_for_error()
    # ne déclenche à tort sa détection "réponse HTML" avec un MagicMock
    # non configuré (dont .get()/.lower() renverraient d'autres Mocks).
    mock.headers = headers if headers is not None else {"Content-Type": "application/json"}
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
    # get_records() sans `fields` : 1) lit le schéma pour connaître les
    # champs, 2) interroge /query/columns en paginant via `window`
    # jusqu'à couvoir `totalRows`. Simule 2 pages de résultats.
    mock_req.side_effect = [
        make_mock_response(200, {  # GET /resources/form/form001/schema
            "id": "form001", "label": "Enquête", "databaseId": "db001",
            "elements": [
                {"id": "f1", "label": "Nom", "type": "FREE_TEXT",
                 "code": "NOM", "required": False, "key": False},
            ],
        }),
        make_mock_response(200, {  # POST /resources/query/columns (page 1)
            "rows": 2, "totalRows": 3,
            "columns": [
                {"id": "_id", "storage": "array", "values": ["r1", "r2"]},
                {"id": "_lastEditTime", "storage": "array", "values": [1000, 1001]},
                {"id": "NOM", "storage": "array", "values": ["Alice", "Bob"]},
            ],
        }),
        make_mock_response(200, {  # POST /resources/query/columns (page 2)
            "rows": 1, "totalRows": 3,
            "columns": [
                {"id": "_id", "storage": "array", "values": ["r3"]},
                {"id": "_lastEditTime", "storage": "array", "values": [1002]},
                {"id": "NOM", "storage": "array", "values": ["Charlie"]},
            ],
        }),
    ]
    records = client.get_records("form001")
    assert len(records) == 3
    assert records[0].record_id == "r1"
    assert records[0].values["NOM"] == "Alice"
    assert records[2].values["NOM"] == "Charlie"
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
    assert f["type"] == "quantity"  # type réel confirmé (minuscule), pas "QUANTITY"
    assert f["typeParameters"]["units"] == "personnes"
    assert f["typeParameters"]["aggregation"] == "SUM"


def test_single_select_field_creation():
    f = single_select_field("Sexe", ["Homme", "Femme", "Autre"], code="SEXE")
    # Type réel confirmé : "enumerated" avec cardinality "single" — il
    # n'existe pas de type "SINGLE_SELECTION" séparé côté serveur.
    assert f["type"] == "enumerated"
    assert f["typeParameters"]["cardinality"] == "single"
    assert len(f["typeParameters"]["values"]) == 3


def test_multi_select_field_creation():
    f = multi_select_field("Besoins", ["Eau", "Nourriture", "Abri"], code="NEEDS")
    assert f["type"] == "enumerated"
    assert f["typeParameters"]["cardinality"] == "multiple"


def test_field_from_dict_enumerated():
    """Vérifie le parsing d'un vrai champ 'enumerated' tel que renvoyé
    par le serveur (confirmé sur un schéma réel)."""
    data = {
        "id": "f1", "label": "Sexe", "type": "enumerated", "code": "SEXE",
        "required": False, "key": False,
        "typeParameters": {
            "cardinality": "single",
            "presentation": "automatic",
            "values": [
                {"id": "o1", "label": "Homme"},
                {"id": "o2", "label": "Femme"},
            ],
        },
    }
    f = Field.from_dict(data)
    assert f.type == "enumerated"
    assert f.cardinality == "single"
    assert len(f.options) == 2
    assert f.options[0].label == "Homme"


def test_field_from_dict_quantity_lowercase():
    """Le serveur renvoie 'quantity' en minuscule, pas 'QUANTITY'."""
    data = {
        "id": "f1", "label": "Age", "type": "quantity", "code": "AGE",
        "required": False, "key": False,
        "typeParameters": {"units": "ans", "aggregation": "SUM"},
    }
    f = Field.from_dict(data)
    assert f.type == "quantity"
    assert f.units == "ans"


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
    # L'API réelle utilise des états en minuscules ("started"/"completed"),
    # pas "RUNNING"/"COMPLETED" en majuscules (voir R : executeJob()).
    mock_req.side_effect = [
        make_mock_response(200, {"state": "started"}),
        make_mock_response(200, {"state": "completed", "result": "ok"}),
    ]
    result = client._wait_for_job("job001", poll_interval=0)
    assert result["state"] == "completed"


@patch("requests.Session.request")
def test_wait_for_job_failure(mock_req, client):
    mock_req.return_value = make_mock_response(200, {
        "state": "failed",
        "error": {"message": "Erreur d'import"}
    })
    with pytest.raises(JobError):
        client._wait_for_job("job002", poll_interval=0)


# ─── TESTS : CORRECTION DU PRÉFIXE /resources ET DES PAYLOADS RÉELS ──────────

@patch("requests.Session.request")
def test_requests_use_resources_prefix(mock_req, client):
    """Toutes les requêtes doivent cibler /resources/..., pas /api/...
    (c'était la cause racine des NotFoundError observées en usage réel)."""
    mock_req.return_value = make_mock_response(200, [])
    client.get_databases()
    called_url = mock_req.call_args.args[1] if len(mock_req.call_args.args) > 1 \
        else mock_req.call_args.kwargs.get("url")
    assert "/resources/databases" in called_url
    assert "/api/" not in called_url


@patch("requests.Session.request")
def test_delete_form_requires_database_id(mock_req, client):
    """delete_form() doit poster un diff resourceDeletions vers
    /resources/databases/{database_id}, pas un DELETE /form/{id} direct
    (qui n'existe pas dans l'API réelle)."""
    mock_req.return_value = make_mock_response(200, {})
    client.delete_form("db001", "form001")
    called_url = mock_req.call_args.args[1] if len(mock_req.call_args.args) > 1 \
        else mock_req.call_args.kwargs.get("url")
    sent_json = mock_req.call_args.kwargs.get("json")
    assert "/resources/databases/db001" in called_url
    assert sent_json["resourceDeletions"] == ["form001"]


@patch("requests.Session.request")
def test_add_database_user_nested_role_payload(mock_req, client):
    """L'API réelle attend un objet "role" imbriqué {id, parameters,
    resources}, pas un simple "roleId" au niveau racine."""
    mock_req.return_value = make_mock_response(200, {
        "userId": 42, "email": "a@b.org", "name": "Alice", "roleId": "admin"
    })
    client.add_database_user("db001", "a@b.org", "Alice", role_id="admin")
    sent_json = mock_req.call_args.kwargs.get("json")
    assert sent_json["role"]["id"] == "admin"
    assert "roleId" not in sent_json


@patch("requests.Session.request")
def test_update_form_schema_is_post_with_nested_response(mock_req, client):
    """update_form_schema() doit faire un POST (pas un PUT) et lire la
    réponse imbriquée sous forms[0].schema."""
    from activityinfo.models.form import FormSchema
    schema = FormSchema(id="form001", label="Test", database_id="db001", fields=[])
    mock_req.return_value = make_mock_response(200, {
        "forms": [{"id": "form001", "schema": {
            "id": "form001", "label": "Test modifié", "databaseId": "db001",
            "elements": [],
        }}]
    })
    updated = client.update_form_schema(schema)
    assert mock_req.call_args.args[0] == "POST"
    assert updated.label == "Test modifié"


@patch("requests.Session.request")
def test_add_field_appends_and_uploads(mock_req, client):
    """add_field() doit : 1) lire le schéma existant, 2) y ajouter le
    nouveau champ, 3) poster le schéma complet mis à jour."""
    from activityinfo.models.field import text_field
    mock_req.side_effect = [
        make_mock_response(200, {  # GET schema existant (1 champ)
            "id": "form001", "label": "Test", "databaseId": "db001",
            "elements": [
                {"id": "f1", "label": "Nom", "type": "FREE_TEXT",
                 "code": "NOM", "required": False, "key": False},
            ],
        }),
        make_mock_response(200, {  # POST update -> schéma avec 2 champs
            "forms": [{"id": "form001", "schema": {
                "id": "form001", "label": "Test", "databaseId": "db001",
                "elements": [
                    {"id": "f1", "label": "Nom", "type": "FREE_TEXT",
                     "code": "NOM", "required": False, "key": False},
                    {"id": "f2", "label": "Commentaire", "type": "FREE_TEXT",
                     "code": "COMMENT", "required": False, "key": False},
                ],
            }}]
        }),
    ]
    updated = client.add_field("form001", text_field("Commentaire", code="COMMENT"))
    assert len(updated.fields) == 2
    assert mock_req.call_args_list[1].args[0] == "POST"


@patch("requests.Session.request")
def test_add_field_avoids_code_collision(mock_req, client):
    """Si le code du nouveau champ existe déjà, add_field() doit en
    générer un autre plutôt que d'envoyer un schéma avec un code en
    double au serveur (comme le fait addFormField() côté R)."""
    from activityinfo.models.field import text_field
    mock_req.side_effect = [
        make_mock_response(200, {
            "id": "form001", "label": "Test", "databaseId": "db001",
            "elements": [
                {"id": "f1", "label": "Nom", "type": "FREE_TEXT",
                 "code": "NOM", "required": False, "key": False},
            ],
        }),
        make_mock_response(200, {"forms": [{"id": "form001", "schema": {
            "id": "form001", "label": "Test", "databaseId": "db001",
            "elements": [],
        }}]}),
    ]
    client.add_field("form001", text_field("Nom bis", code="NOM"))
    sent_json = mock_req.call_args_list[1].kwargs.get("json")
    sent_codes = [e.get("code") for e in sent_json["elements"]]
    assert sent_codes.count("NOM") == 1  # pas de doublon envoyé au serveur


@patch("requests.Session.request")
def test_delete_field_by_code(mock_req, client):
    """delete_field(code=...) doit retirer le champ correspondant et
    poster le schéma sans lui."""
    mock_req.side_effect = [
        make_mock_response(200, {  # GET schema (2 champs)
            "id": "form001", "label": "Test", "databaseId": "db001",
            "elements": [
                {"id": "f1", "label": "Nom", "type": "FREE_TEXT",
                 "code": "NOM", "required": False, "key": False},
                {"id": "f2", "label": "Commentaire", "type": "FREE_TEXT",
                 "code": "COMMENT", "required": False, "key": False},
            ],
        }),
        make_mock_response(200, {  # POST update -> schéma avec 1 champ
            "forms": [{"id": "form001", "schema": {
                "id": "form001", "label": "Test", "databaseId": "db001",
                "elements": [
                    {"id": "f1", "label": "Nom", "type": "FREE_TEXT",
                     "code": "NOM", "required": False, "key": False},
                ],
            }}]
        }),
    ]
    updated = client.delete_field("form001", code="COMMENT")
    assert len(updated.fields) == 1
    sent_json = mock_req.call_args_list[1].kwargs.get("json")
    sent_codes = [e.get("code") for e in sent_json["elements"]]
    assert "COMMENT" not in sent_codes
    assert "NOM" in sent_codes


@patch("requests.Session.request")
def test_delete_field_ambiguous_label_raises(mock_req, client):
    """Si plusieurs champs partagent le même label, delete_field(label=...)
    doit lever ValidationError plutôt que de supprimer au hasard (comme
    le fait deleteFormField() côté R)."""
    mock_req.return_value = make_mock_response(200, {
        "id": "form001", "label": "Test", "databaseId": "db001",
        "elements": [
            {"id": "f1", "label": "Commentaire", "type": "FREE_TEXT",
             "code": "C1", "required": False, "key": False},
            {"id": "f2", "label": "Commentaire", "type": "FREE_TEXT",
             "code": "C2", "required": False, "key": False},
        ],
    })
    with pytest.raises(ValidationError):
        client.delete_field("form001", label="Commentaire")


@patch("requests.Session.request")
def test_delete_field_not_found_returns_unchanged(mock_req, client):
    """Si aucun champ ne correspond, on ne poste rien et on renvoie le
    schéma tel quel (pas d'exception, juste un avertissement)."""
    mock_req.return_value = make_mock_response(200, {
        "id": "form001", "label": "Test", "databaseId": "db001",
        "elements": [
            {"id": "f1", "label": "Nom", "type": "FREE_TEXT",
             "code": "NOM", "required": False, "key": False},
        ],
    })
    result = client.delete_field("form001", code="INEXISTANT")
    assert len(result.fields) == 1
    assert mock_req.call_count == 1  # un seul appel (le GET), pas de POST


@patch("requests.Session.request")
def test_delete_field_requires_exactly_one_identifier(mock_req, client):
    """Ni zéro ni plusieurs identifiants ne doivent être acceptés."""
    with pytest.raises(ValidationError):
        client.delete_field("form001")
    with pytest.raises(ValidationError):
        client.delete_field("form001", field_id="f1", code="NOM")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
