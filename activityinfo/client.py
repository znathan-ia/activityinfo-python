"""
activityinfo.client
~~~~~~~~~~~~~~~~~~~
Client principal ActivityInfo Python.
Inspiré du package R bedatadriven/activityinfo-R.

Usage :
    from activityinfo import ActivityInfoClient
    client = ActivityInfoClient("votre_token")
    databases = client.get_databases()
"""

import logging
import time
from typing import Optional, List, Dict, Any, Iterator

from .exceptions import ActivityInfoError, JobError, ValidationError
from .utils.http import build_session, safe_request, BASE_URL
from .utils.cuid import generate_cuid
from .models.database import Database, DatabaseResource, DatabaseUser
from .models.form import FormSchema, FormRecord
from .models.field import Field

logger = logging.getLogger("activityinfo")


class ActivityInfoClient:
    """
    Client complet pour l'API ActivityInfo REST.

    Équivalent Python du package R bedatadriven/activityinfo-R.

    Paramètres
    ----------
    token : str
        Token d'authentification personnel ActivityInfo.
        Générer sur : Profil > Paramètres > Tokens API
    server_url : str, optionnel
        URL du serveur (défaut : https://www.activityinfo.org).
        Utile pour les déploiements ActivityInfo Self-Managed.
    timeout : int
        Timeout des requêtes HTTP en secondes (défaut : 30).
    log_level : int
        Niveau de logging (défaut : WARNING).

    Exemple
    -------
    >>> client = ActivityInfoClient("mon_token")
    >>> dbs = client.get_databases()
    >>> for db in dbs:
    ...     print(db.label)
    """

    def __init__(
        self,
        token: str,
        server_url: str = BASE_URL,
        timeout: int = 30,
        log_level: int = logging.WARNING,
    ):
        if not token:
            raise ValidationError("Le token d'authentification est requis.")

        logging.basicConfig(level=log_level)
        self._token = token
        self._base_url = server_url.rstrip("/")
        self._session = build_session(token, timeout)
        logger.info(f"ActivityInfoClient initialisé sur {self._base_url}")

    # ─── MÉTHODES HTTP PRIVÉES ─────────────────────────────────────────────────

    def _get(self, path: str, **kwargs) -> Any:
        return safe_request(self._session, "GET",
                            f"{self._base_url}{path}", **kwargs)

    def _post(self, path: str, json: dict = None, **kwargs) -> Any:
        return safe_request(self._session, "POST",
                            f"{self._base_url}{path}", json=json, **kwargs)

    def _put(self, path: str, json: dict = None, **kwargs) -> Any:
        return safe_request(self._session, "PUT",
                            f"{self._base_url}{path}", json=json, **kwargs)

    def _delete(self, path: str, **kwargs) -> Any:
        return safe_request(self._session, "DELETE",
                            f"{self._base_url}{path}", **kwargs)

    # ─── PING ──────────────────────────────────────────────────────────────────

    def ping(self) -> bool:
        """Vérifie la connexion au serveur ActivityInfo."""
        try:
            self._get("/api/ping")
            return True
        except ActivityInfoError:
            return False

    # ══════════════════════════════════════════════════════════════════════════
    # BASES DE DONNÉES
    # Équivalent R : getDatabases(), getDatabaseResources(), getDatabaseTree()
    # ══════════════════════════════════════════════════════════════════════════

    def get_databases(self) -> List[Database]:
        """
        Liste toutes les bases de données accessibles.
        Équivalent R : getDatabases()

        Retourne
        --------
        List[Database]
        """
        data = self._get("/api/databases")
        return [Database.from_dict(d) for d in data]

    def get_database(self, database_id: str) -> Database:
        """
        Récupère une base de données par son ID.
        Équivalent R : getDatabaseTree()
        """
        data = self._get(f"/api/databases/{database_id}")
        return Database.from_dict(data)

    def get_database_resources(self, database_id: str
                                ) -> List[DatabaseResource]:
        """
        Liste toutes les ressources d'une base (formulaires, dossiers...).
        Équivalent R : getDatabaseResources()

        Retourne
        --------
        List[DatabaseResource]
        """
        data = self._get(f"/api/databases/{database_id}/resources")
        resources = data if isinstance(data, list) else data.get("resources", [])
        return [DatabaseResource.from_dict(r) for r in resources]

    def add_database(self, label: str,
                     description: str = None) -> Database:
        """
        Crée une nouvelle base de données.
        Équivalent R : addDatabase()
        """
        payload = {"label": label}
        if description:
            payload["description"] = description
        data = self._post("/api/databases", json=payload)
        return Database.from_dict(data)

    def delete_database(self, database_id: str) -> None:
        """Supprime une base de données."""
        self._delete(f"/api/databases/{database_id}")
        logger.info(f"Base supprimée : {database_id}")

    # ══════════════════════════════════════════════════════════════════════════
    # FORMULAIRES
    # Équivalent R : getFormSchema(), addForm(), updateFormSchema()
    # ══════════════════════════════════════════════════════════════════════════

    def get_form_schema(self, form_id: str) -> FormSchema:
        """
        Récupère le schéma complet d'un formulaire.
        Équivalent R : getFormSchema()

        Paramètres
        ----------
        form_id : str
            ID du formulaire (visible dans l'URL du navigateur après "form/")
        """
        data = self._get(f"/api/form/{form_id}/schema")
        return FormSchema.from_dict(data)

    def add_form(self, database_id: str, label: str,
                 elements: List[dict],
                 folder_id: str = None,
                 description: str = None) -> FormSchema:
        """
        Crée un nouveau formulaire dans une base de données.
        Équivalent R : addForm()

        Paramètres
        ----------
        database_id : str
        label : str
        elements : List[dict]
            Liste de champs créés avec text_field(), quantity_field(), etc.
        folder_id : str, optionnel
            ID du dossier parent
        description : str, optionnel
        """
        form_id = generate_cuid()
        payload = {
            "id": form_id,
            "databaseId": database_id,
            "label": label,
            "elements": elements,
        }
        if folder_id:
            payload["folderId"] = folder_id
        if description:
            payload["description"] = description

        self._put(f"/api/form/{form_id}/schema", json=payload)
        return self.get_form_schema(form_id)

    def update_form_schema(self, schema: FormSchema) -> FormSchema:
        """
        Met à jour le schéma d'un formulaire existant.
        Équivalent R : updateFormSchema()
        """
        self._put(f"/api/form/{schema.id}/schema", json=schema.to_dict())
        return self.get_form_schema(schema.id)

    def delete_form(self, form_id: str) -> None:
        """Supprime un formulaire."""
        self._delete(f"/api/form/{form_id}")

    # ══════════════════════════════════════════════════════════════════════════
    # ENREGISTREMENTS
    # Équivalent R : getRecords(), addRecord(), updateRecord(),
    #               deleteRecord(), recoverRecord(), importRecords()
    # ══════════════════════════════════════════════════════════════════════════

    def get_records(self, form_id: str,
                    fields: List[str] = None) -> List[FormRecord]:
        """
        Récupère tous les enregistrements d'un formulaire
        avec pagination automatique.
        Équivalent R : getRecords() |> collect()

        Paramètres
        ----------
        form_id : str
        fields : List[str], optionnel
            Liste de codes de champs à inclure (tous si None)
        """
        all_records = []
        cursor = None

        while True:
            params: Dict[str, Any] = {}
            if cursor:
                params["cursor"] = cursor
            if fields:
                params["fields"] = ",".join(fields)

            data = self._get(f"/api/form/{form_id}/records", params=params)

            items = data.get("items", [])
            all_records.extend([
                FormRecord.from_dict(item, form_id) for item in items
            ])

            cursor = data.get("cursor")
            if not cursor:
                break

        logger.info(f"{len(all_records)} enregistrements récupérés "
                    f"depuis {form_id}")
        return all_records

    def get_record(self, form_id: str, record_id: str) -> FormRecord:
        """
        Récupère un enregistrement unique.
        Équivalent R : getRecord()
        """
        data = self._get(f"/api/form/{form_id}/record/{record_id}")
        return FormRecord.from_dict(data, form_id)

    def add_record(self, form_id: str,
                   field_values: Dict[str, Any]) -> FormRecord:
        """
        Ajoute un nouvel enregistrement.
        Équivalent R : addRecord()

        Paramètres
        ----------
        form_id : str
        field_values : dict
            Dictionnaire {code_champ: valeur}

        Exemple
        -------
        >>> client.add_record("cxy123", {
        ...     "NAME": "Alice Jones",
        ...     "AGE": 32,
        ...     "DATE": "2024-01-15"
        ... })
        """
        record_id = generate_cuid()
        payload = {
            "changes": [{
                "recordId": record_id,
                "formId": form_id,
                "fields": field_values,
            }]
        }
        self._post("/api/update", json=payload)
        return self.get_record(form_id, record_id)

    def update_record(self, form_id: str, record_id: str,
                      field_values: Dict[str, Any]) -> FormRecord:
        """
        Met à jour un enregistrement existant.
        Équivalent R : updateRecord()
        """
        payload = {
            "changes": [{
                "recordId": record_id,
                "formId": form_id,
                "fields": field_values,
            }]
        }
        self._post("/api/update", json=payload)
        return self.get_record(form_id, record_id)

    def delete_record(self, form_id: str, record_id: str) -> None:
        """
        Supprime un enregistrement.
        Équivalent R : deleteRecord()
        """
        payload = {
            "changes": [{
                "recordId": record_id,
                "formId": form_id,
                "deleted": True,
            }]
        }
        self._post("/api/update", json=payload)
        logger.info(f"Enregistrement supprimé : {record_id}")

    def recover_record(self, form_id: str, record_id: str) -> FormRecord:
        """
        Restaure un enregistrement supprimé.
        Équivalent R : recoverRecord()
        """
        self._post(
            f"/api/form/{form_id}/record/{record_id}/recover"
        )
        return self.get_record(form_id, record_id)

    def get_record_history(self, form_id: str,
                           record_id: str) -> List[dict]:
        """
        Récupère l'historique des modifications d'un enregistrement.
        Équivalent R : getRecordHistory()
        """
        return self._get(
            f"/api/form/{form_id}/record/{record_id}/history"
        )

    def import_records(self, form_id: str,
                       records: List[Dict[str, Any]],
                       wait: bool = True,
                       poll_interval: int = 2) -> dict:
        """
        Importe plusieurs enregistrements en masse (job asynchrone).
        Équivalent R : importRecords()

        Paramètres
        ----------
        form_id : str
        records : List[dict]
            Liste de dictionnaires {code_champ: valeur}
        wait : bool
            Attendre la fin du job (défaut : True)
        poll_interval : int
            Intervalle de polling en secondes (défaut : 2)
        """
        changes = [
            {"recordId": generate_cuid(), "formId": form_id, "fields": r}
            for r in records
        ]
        payload = {"changes": changes}
        job_data = self._post("/api/jobs/import", json=payload)
        job_id = job_data.get("jobId")

        if wait and job_id:
            return self._wait_for_job(job_id, poll_interval)

        return job_data

    # ── Import depuis pandas DataFrame ────────────────────────────────────────

    def import_dataframe(self, form_id: str, df,
                         field_mapping: Dict[str, str] = None,
                         wait: bool = True) -> dict:
        """
        Importe un DataFrame pandas dans un formulaire ActivityInfo.
        Bonus Python (pas d'équivalent direct en R).

        Paramètres
        ----------
        form_id : str
        df : pandas.DataFrame
        field_mapping : dict, optionnel
            {colonne_df: code_champ_activityinfo}
            Si None, utilise les noms de colonnes directement.
        wait : bool

        Exemple
        -------
        >>> client.import_dataframe("cxy123", df, field_mapping={
        ...     "nom_colonne_excel": "CODE_CHAMP_AI"
        ... })
        """
        if field_mapping:
            df = df.rename(columns=field_mapping)

        # Convertir en liste de dicts, ignorer les NaN
        records = []
        for _, row in df.iterrows():
            record = {
                k: (None if (hasattr(v, '__class__') and
                             v.__class__.__name__ == 'float' and
                             str(v) == 'nan') else v)
                for k, v in row.items()
            }
            records.append(record)

        logger.info(f"Import de {len(records)} lignes vers {form_id}")
        return self.import_records(form_id, records, wait=wait)

    # ── Export vers pandas DataFrame ──────────────────────────────────────────

    def to_dataframe(self, form_id: str, fields: List[str] = None):
        """
        Exporte un formulaire directement en DataFrame pandas.
        Bonus Python (pas d'équivalent direct en R).

        Retourne
        --------
        pandas.DataFrame
        """
        try:
            import pandas as pd
        except ImportError:
            raise ActivityInfoError(
                "pandas est requis : pip install pandas"
            )

        records = self.get_records(form_id, fields=fields)
        if not records:
            return pd.DataFrame()

        rows = []
        for rec in records:
            row = {"_id": rec.record_id, "_lastEditTime": rec.last_edit_time}
            row.update(rec.values)
            rows.append(row)

        return pd.DataFrame(rows)

    # ══════════════════════════════════════════════════════════════════════════
    # UTILISATEURS
    # Équivalent R : getDatabaseUsers(), addDatabaseUser(),
    #               deleteDatabaseUser(), updateDatabaseUserRole()
    # ══════════════════════════════════════════════════════════════════════════

    def get_database_users(self, database_id: str) -> List[DatabaseUser]:
        """
        Liste les utilisateurs d'une base de données.
        Équivalent R : getDatabaseUsers()
        """
        from .models.database import DatabaseUser
        data = self._get(f"/api/databases/{database_id}/users")
        users = data if isinstance(data, list) else data.get("users", [])
        return [DatabaseUser.from_dict(u) for u in users]

    def add_database_user(self, database_id: str, email: str,
                          name: str, role_id: str,
                          locale: str = "fr") -> DatabaseUser:
        """
        Ajoute un utilisateur à une base de données.
        Équivalent R : addDatabaseUser()
        """
        from .models.database import DatabaseUser
        payload = {
            "email": email,
            "name": name,
            "locale": locale,
            "roleId": role_id,
        }
        data = self._post(
            f"/api/databases/{database_id}/users", json=payload
        )
        return DatabaseUser.from_dict(data)

    def delete_database_user(self, database_id: str,
                             user_id: int) -> None:
        """
        Retire un utilisateur d'une base de données.
        Équivalent R : deleteDatabaseUser()
        """
        self._delete(
            f"/api/databases/{database_id}/users/{user_id}"
        )

    def update_database_user_role(self, database_id: str,
                                  user_id: int,
                                  role_id: str) -> None:
        """
        Met à jour le rôle d'un utilisateur.
        Équivalent R : updateDatabaseUserRole()
        """
        self._put(
            f"/api/databases/{database_id}/users/{user_id}/role",
            json={"roleId": role_id}
        )

    # ══════════════════════════════════════════════════════════════════════════
    # REQUÊTES / QUERIES
    # Équivalent R : queryTable(), queryColumns()
    # ══════════════════════════════════════════════════════════════════════════

    def query_table(self, form_id: str,
                    columns: List[str] = None,
                    filter_expr: str = None) -> List[dict]:
        """
        Exécute une requête sur un formulaire.
        Équivalent R : queryTable()
        """
        payload: Dict[str, Any] = {"form": form_id}
        if columns:
            payload["columns"] = {col: {"type": "field", "id": col}
                                   for col in columns}
        if filter_expr:
            payload["filter"] = filter_expr

        return self._post("/api/query/rows", json=payload)

    def query_columns(self, form_id: str,
                      columns: Dict[str, dict]) -> dict:
        """
        Requête par colonnes (format analytique).
        Équivalent R : queryColumns()
        """
        payload = {"form": form_id, "columns": columns}
        return self._post("/api/query/columns", json=payload)

    # ══════════════════════════════════════════════════════════════════════════
    # PIÈCES JOINTES
    # Équivalent R : getAttachment()
    # ══════════════════════════════════════════════════════════════════════════

    def get_attachment(self, form_id: str, record_id: str,
                       field_id: str, blob_id: str) -> bytes:
        """
        Télécharge une pièce jointe.
        Équivalent R : getAttachment()
        """
        response = self._session.get(
            f"{self._base_url}/api/form/{form_id}/record/"
            f"{record_id}/field/{field_id}/blob/{blob_id}"
        )
        return response.content

    def get_form_geojson(self, form_id: str) -> dict:
        """
        Récupère les données géographiques d'un formulaire en GeoJSON.
        Équivalent R : getFormGeoJson()
        """
        return self._get(f"/api/form/{form_id}/geo")

    # ══════════════════════════════════════════════════════════════════════════
    # JOBS ASYNCHRONES
    # ══════════════════════════════════════════════════════════════════════════

    def get_job_status(self, job_id: str) -> dict:
        """Récupère le statut d'un job asynchrone."""
        return self._get(f"/api/jobs/{job_id}")

    def _wait_for_job(self, job_id: str,
                      poll_interval: int = 2,
                      max_wait: int = 300) -> dict:
        """
        Attend la fin d'un job asynchrone avec polling.
        Lève JobError si le job échoue ou dépasse max_wait secondes.
        """
        elapsed = 0
        while elapsed < max_wait:
            status = self.get_job_status(job_id)
            state = status.get("state", "")

            if state == "COMPLETED":
                logger.info(f"Job {job_id} terminé avec succès")
                return status
            elif state == "FAILED":
                msg = status.get("error", {}).get("message", "Échec inconnu")
                raise JobError(f"Job {job_id} échoué : {msg}", job_id)

            logger.debug(f"Job {job_id} en cours ({state})... "
                         f"{elapsed}s écoulées")
            time.sleep(poll_interval)
            elapsed += poll_interval

        raise JobError(
            f"Job {job_id} : délai maximum de {max_wait}s dépassé",
            job_id
        )

    # ══════════════════════════════════════════════════════════════════════════
    # COMPTE
    # ══════════════════════════════════════════════════════════════════════════

    def get_account_status(self) -> dict:
        """Récupère le statut du compte utilisateur actuel."""
        return self._get("/api/account/status")

    def __repr__(self):
        return f"ActivityInfoClient(server={self._base_url!r})"
