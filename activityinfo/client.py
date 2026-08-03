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
from .utils.http import build_session, safe_request, safe_request_binary, BASE_URL
from .utils.cuid import generate_cuid
from .models.database import Database, DatabaseResource, DatabaseUser
from .models.form import FormSchema, FormRecord
from .models.field import Field

logger = logging.getLogger("activityinfo")

# Tous les endpoints de l'API ActivityInfo sont sous ce préfixe.
# Voir modify_url(activityInfoRootUrl(), path = c("resources", path))
# dans R/rest.R : le préfixe est "resources", pas "api".
_RESOURCES_PREFIX = "/resources"


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
                            f"{self._base_url}{_RESOURCES_PREFIX}{path}", **kwargs)

    def _post(self, path: str, json: dict = None, **kwargs) -> Any:
        return safe_request(self._session, "POST",
                            f"{self._base_url}{_RESOURCES_PREFIX}{path}", json=json, **kwargs)

    def _put(self, path: str, json: dict = None, **kwargs) -> Any:
        return safe_request(self._session, "PUT",
                            f"{self._base_url}{_RESOURCES_PREFIX}{path}", json=json, **kwargs)

    def _delete(self, path: str, **kwargs) -> Any:
        return safe_request(self._session, "DELETE",
                            f"{self._base_url}{_RESOURCES_PREFIX}{path}", **kwargs)

    # ─── PING ──────────────────────────────────────────────────────────────────

    def ping(self) -> bool:
        """
        Vérifie la connexion au serveur ActivityInfo.

        NB : il n'y a pas d'endpoint /ping confirmé dans le code source R
        lu pour ce projet. Cette méthode utilise get_databases() comme
        vérification de connectivité/authentification à la place.
        """
        try:
            self.get_databases()
            return True
        except ActivityInfoError:
            return False

    # ══════════════════════════════════════════════════════════════════════════
    # BASES DE DONNÉES
    # Équivalent R : getDatabases(), getDatabaseResources(), getDatabaseTree()
    # Voir R/databases.R
    # ══════════════════════════════════════════════════════════════════════════

    def get_databases(self) -> List[Database]:
        """
        Liste toutes les bases de données accessibles.
        Équivalent R : getDatabases() -> GET /resources/databases
        """
        data = self._get("/databases")
        return [Database.from_dict(d) for d in data]

    def get_database(self, database_id: str) -> Database:
        """
        Récupère les métadonnées d'une base de données par son ID.
        Équivalent R : getDatabaseTree() -> GET /resources/databases/{id}

        NB : la réponse complète est un "database tree" qui contient
        aussi la liste des ressources (voir get_database_resources).
        """
        data = self._get(f"/databases/{database_id}")
        return Database.from_dict(data)

    def get_database_resources(self, database_id: str
                                ) -> List[DatabaseResource]:
        """
        Liste toutes les ressources d'une base (formulaires, dossiers...).
        Équivalent R : getDatabaseResources() / getDatabaseTree()$resources

        NB : il n'existe pas d'endpoint séparé "/resources" pour cette
        liste — elle est incluse dans la réponse de GET /databases/{id}
        (le "database tree"), sous la clé "resources".
        """
        tree = self._get(f"/databases/{database_id}")
        resources = tree.get("resources", []) if isinstance(tree, dict) else []
        return [DatabaseResource.from_dict(r) for r in resources]

    def add_database(self, label: str, database_id: str = None) -> Database:
        """
        Crée une nouvelle base de données.
        Équivalent R : addDatabase() -> POST /resources/databases
        body: {id, label, templateId: "blank"}

        Paramètres
        ----------
        label : str
        database_id : str, optionnel
            Un CUID est généré automatiquement si non fourni.

        NB : contrairement à une version précédente, cette méthode
        n'envoie pas de champ "description" — R/databases.R montre que
        l'API n'en attend pas à la création (seuls id/label/templateId
        sont envoyés).
        """
        payload = {
            "id": database_id or generate_cuid(),
            "label": label,
            "templateId": "blank",
        }
        data = self._post("/databases", json=payload)
        return Database.from_dict(data)

    def delete_database(self, database_id: str) -> None:
        """
        Supprime une base de données.
        Équivalent R : deleteDatabase() -> DELETE /resources/databases/{id}
        """
        self._delete(f"/databases/{database_id}")
        logger.info(f"Base supprimée : {database_id}")

    # ══════════════════════════════════════════════════════════════════════════
    # FORMULAIRES
    # Équivalent R : getFormSchema(), addForm(), updateFormSchema(), deleteForm()
    # Voir R/forms.R
    # ══════════════════════════════════════════════════════════════════════════

    def get_form_schema(self, form_id: str) -> FormSchema:
        """
        Récupère le schéma complet d'un formulaire.
        Équivalent R : getFormSchema() -> GET /resources/form/{id}/schema
        """
        data = self._get(f"/form/{form_id}/schema")
        return FormSchema.from_dict(data)

    def add_form(self, database_id: str, label: str,
                 elements: List[dict],
                 parent_id: str = None,
                 description: str = None) -> FormSchema:
        """
        Crée un nouveau formulaire dans une base de données.
        Équivalent R : addForm.formSchema() ->
        POST /resources/databases/{databaseId}/forms
        body: {formResource: {id, parentId, type: "FORM", label,
                               visibility: "PRIVATE"},
               formClass: {id, databaseId, label, elements, ...}}

        Paramètres
        ----------
        database_id : str
        label : str
        elements : List[dict]
            Liste de champs créés avec text_field(), quantity_field(), etc.
        parent_id : str, optionnel
            ID de la base ou du dossier parent (par défaut : database_id).
            Remplace l'ancien paramètre folder_id.
        description : str, optionnel

        La réponse de l'API contient tous les formulaires affectés
        (result["forms"], une liste). On extrait ici uniquement le
        formulaire dont l'id correspond à celui qu'on vient de créer.
        """
        form_id = generate_cuid()
        form_class: Dict[str, Any] = {
            "id": form_id,
            "databaseId": database_id,
            "label": label,
            "elements": elements,
        }
        if description:
            form_class["description"] = description

        payload = {
            "formResource": {
                "id": form_id,
                "parentId": parent_id or database_id,
                "type": "FORM",
                "label": label,
                "visibility": "PRIVATE",
            },
            "formClass": form_class,
        }

        result = self._post(f"/databases/{database_id}/forms", json=payload)

        forms = result.get("forms", []) if isinstance(result, dict) else []
        match = next((f for f in forms if f.get("id") == form_id), None)
        if match is None:
            # Solution de repli : recharger le schéma directement.
            return self.get_form_schema(form_id)
        return FormSchema.from_dict(match["schema"])

    def update_form_schema(self, schema: FormSchema) -> FormSchema:
        """
        Met à jour le schéma d'un formulaire existant.
        Équivalent R : updateFormSchema() ->
        POST (et non PUT) /resources/form/{id}/schema
        body: le schéma complet, à plat (pas d'enveloppe formResource).
        """
        result = self._post(f"/form/{schema.id}/schema", json=schema.to_dict())
        forms = result.get("forms", []) if isinstance(result, dict) else []
        if forms:
            return FormSchema.from_dict(forms[0]["schema"])
        return self.get_form_schema(schema.id)

    def delete_form(self, database_id: str, form_id: str) -> None:
        """
        Supprime un formulaire.
        Équivalent R : deleteForm() ->
        POST /resources/databases/{databaseId}
        body: un objet de mise à jour de base avec
              resourceDeletions: [formId]

        NB : contrairement à une version précédente, il n'existe pas
        d'endpoint dédié DELETE /form/{id}. La suppression d'un
        formulaire passe par une mise à jour de la base de données qui
        le contient — d'où le nouveau paramètre database_id, requis.
        """
        payload = {
            "resourceUpdates": [],
            "resourceDeletions": [form_id],
            "lockUpdates": [],
            "lockDeletions": [],
            "roleUpdates": [],
            "roleDeletions": [],
            "languageUpdates": [],
            "languageDeletions": [],
        }
        self._post(f"/databases/{database_id}", json=payload)
        logger.info(f"Formulaire supprimé : {form_id} (base {database_id})")

    # ══════════════════════════════════════════════════════════════════════════
    # ENREGISTREMENTS
    # Équivalent R : getRecords(), addRecord(), updateRecord(),
    #               deleteRecord(), recoverRecord(), getRecordHistory()
    # Voir R/records.R
    # ══════════════════════════════════════════════════════════════════════════

    def get_records(self, form_id: str,
                    fields: List[str] = None,
                    page_size: int = 1000) -> List[FormRecord]:
        """
        Récupère tous les enregistrements d'un formulaire.

        NB : il n'existe pas d'endpoint GET .../records avec pagination
        par curseur (l'hypothèse d'une version précédente). Le package R
        récupère les enregistrements via le mécanisme de requête
        colonnaire POST /resources/query/columns (voir queryTable() dans
        R/tableQuery.R). Cette méthode reproduit ce mécanisme et pagine
        par fenêtre (offset/limite) plutôt que par curseur.

        Paramètres
        ----------
        form_id : str
        fields : List[str], optionnel
            Codes de champs à inclure (tous les champs du schéma si None)
        page_size : int
            Taille de fenêtre pour la pagination (défaut : 1000)
        """
        columns = [
            {"id": "_id", "expression": "_id"},
            {"id": "_lastEditTime", "expression": "_lastEditTime"},
        ]
        if fields:
            columns += [{"id": f, "expression": f} for f in fields]
        else:
            schema = self.get_form_schema(form_id)
            for f in schema.fields:
                code = f.code or f.id
                columns.append({"id": code, "expression": code})

        all_rows: List[Dict[str, Any]] = []
        offset = 0
        while True:
            payload = {
                "rowSources": [{"rootFormId": form_id}],
                "columns": columns,
                "truncateStrings": False,
                "window": [offset, page_size],
            }
            result = self._post("/query/columns", json=payload)
            rows = self._column_set_to_rows(result)
            all_rows.extend(rows)

            total_rows = result.get("totalRows", len(all_rows))
            offset += page_size
            if not rows or offset >= total_rows:
                break

        records = []
        for row in all_rows:
            record_id = row.get("_id")
            last_edit_time = row.get("_lastEditTime")
            values = {k: v for k, v in row.items()
                      if k not in ("_id", "_lastEditTime")}
            records.append(FormRecord(
                record_id=record_id, form_id=form_id,
                values=values, last_edit_time=last_edit_time,
            ))

        logger.info(f"{len(records)} enregistrements récupérés "
                    f"depuis {form_id}")
        return records

    @staticmethod
    def _column_set_to_rows(column_set: dict) -> List[Dict[str, Any]]:
        """
        Convertit une réponse de requête colonnaire (POST /query/columns)
        en liste de lignes (dicts). Voir parseColumnSet() dans
        R/tableQuery.R pour le format d'origine :
        columnSet = {rows: N, columns: [{id, storage, type, value|values}]}
        où storage vaut "constant", "array" ou "empty".
        """
        n_rows = column_set.get("rows", 0) or 0
        columns = column_set.get("columns", [])

        column_values: Dict[str, List[Any]] = {}
        for col in columns:
            col_id = col.get("id")
            storage = col.get("storage")
            if storage == "constant":
                column_values[col_id] = [col.get("value")] * n_rows
            elif storage == "array":
                values = col.get("values", [])
                if len(values) < n_rows:
                    values = values + [None] * (n_rows - len(values))
                column_values[col_id] = values
            else:  # "empty" ou valeur inconnue -> tout à None
                column_values[col_id] = [None] * n_rows

        rows = []
        for i in range(n_rows):
            rows.append({
                col_id: values[i] for col_id, values in column_values.items()
            })
        return rows

    def get_record(self, form_id: str, record_id: str) -> FormRecord:
        """
        Récupère un enregistrement unique.
        Équivalent R : getRecord() -> GET /resources/form/{id}/record/{id}
        """
        data = self._get(f"/form/{form_id}/record/{record_id}")
        return FormRecord.from_dict(data, form_id)

    def add_record(self, form_id: str,
                   field_values: Dict[str, Any]) -> FormRecord:
        """
        Ajoute un nouvel enregistrement.
        Équivalent R : addRecord() -> POST /resources/update
        body: {changes: [{formId, recordId, fields}]}

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
        self._post("/update", json=payload)
        return self.get_record(form_id, record_id)

    def update_record(self, form_id: str, record_id: str,
                      field_values: Dict[str, Any]) -> FormRecord:
        """
        Met à jour un enregistrement existant.
        Équivalent R : updateRecord() -> POST /resources/update
        """
        payload = {
            "changes": [{
                "recordId": record_id,
                "formId": form_id,
                "fields": field_values,
            }]
        }
        self._post("/update", json=payload)
        return self.get_record(form_id, record_id)

    def delete_record(self, form_id: str, record_id: str) -> None:
        """
        Supprime un enregistrement.
        Équivalent R : deleteRecord() -> POST /resources/update
        body: {changes: [{formId, recordId, deleted: true}]}
        """
        payload = {
            "changes": [{
                "recordId": record_id,
                "formId": form_id,
                "deleted": True,
            }]
        }
        self._post("/update", json=payload)
        logger.info(f"Enregistrement supprimé : {record_id}")

    def recover_record(self, form_id: str, record_id: str) -> FormRecord:
        """
        Restaure un enregistrement supprimé.
        Équivalent R : recoverRecord() ->
        POST /resources/form/{id}/record/{id}/recover
        """
        self._post(f"/form/{form_id}/record/{record_id}/recover")
        return self.get_record(form_id, record_id)

    def get_record_history(self, form_id: str,
                           record_id: str) -> List[dict]:
        """
        Récupère l'historique des modifications d'un enregistrement.
        Équivalent R : getRecordHistory() ->
        GET /resources/form/{id}/record/{id}/history
        """
        data = self._get(f"/form/{form_id}/record/{record_id}/history")
        return data.get("entries", []) if isinstance(data, dict) else data

    def import_records(self, form_id: str,
                       records: List[Dict[str, Any]],
                       chunk_size: int = 500) -> None:
        """
        Importe plusieurs enregistrements en masse.

        NB : contrairement à une version précédente de cette méthode,
        il n'existe pas de job asynchrone dédié aux imports
        (POST /jobs/import n'existe pas). R/records.R et R/pending.R
        montrent que l'import se fait simplement via des appels
        synchrones à POST /resources/update, en plusieurs lots pour les
        gros volumes. Cette méthode ne retourne donc plus de statut de
        job ; elle lève une exception si un lot échoue.

        Paramètres
        ----------
        form_id : str
        records : List[dict]
            Liste de dictionnaires {code_champ: valeur}
        chunk_size : int
            Nombre d'enregistrements envoyés par requête (défaut : 500)
        """
        for start in range(0, len(records), chunk_size):
            batch = records[start:start + chunk_size]
            changes = [
                {"recordId": generate_cuid(), "formId": form_id, "fields": r}
                for r in batch
            ]
            self._post("/update", json={"changes": changes})
            logger.info(f"Lot de {len(batch)} enregistrements importé "
                        f"vers {form_id}")

    # ── Import depuis pandas DataFrame ────────────────────────────────────────

    def import_dataframe(self, form_id: str, df,
                         field_mapping: Dict[str, str] = None,
                         chunk_size: int = 500) -> None:
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
        chunk_size : int

        Exemple
        -------
        >>> client.import_dataframe("cxy123", df, field_mapping={
        ...     "nom_colonne_excel": "CODE_CHAMP_AI"
        ... })
        """
        if field_mapping:
            df = df.rename(columns=field_mapping)

        # Convertir en liste de dicts, en remplaçant les NaN par None.
        # Le test `v != v` est vrai uniquement pour NaN (IEEE 754), et
        # fonctionne pour float, numpy.float64 ou pandas.NA sans avoir à
        # importer numpy/pandas ici.
        records = []
        for _, row in df.iterrows():
            record = {}
            for k, v in row.items():
                try:
                    is_missing = v != v
                except Exception:
                    is_missing = False
                record[k] = None if is_missing else v
            records.append(record)

        logger.info(f"Import de {len(records)} lignes vers {form_id}")
        self.import_records(form_id, records, chunk_size=chunk_size)

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
    #               deleteDatabaseUser(), updateUserRole()
    # Voir R/databases.R
    # ══════════════════════════════════════════════════════════════════════════

    def get_database_users(self, database_id: str) -> List[DatabaseUser]:
        """
        Liste les utilisateurs d'une base de données.
        Équivalent R : getDatabaseUsers() ->
        GET /resources/databases/{id}/users
        """
        data = self._get(f"/databases/{database_id}/users")
        users = data if isinstance(data, list) else data.get("users", [])
        return [DatabaseUser.from_dict(u) for u in users]

    def add_database_user(self, database_id: str, email: str,
                          name: str, role_id: str,
                          role_parameters: Dict[str, Any] = None,
                          role_resources: List[str] = None,
                          locale: str = "fr") -> DatabaseUser:
        """
        Ajoute un utilisateur à une base de données.
        Équivalent R : addDatabaseUser() ->
        POST /resources/databases/{id}/users
        body: {email, name, locale,
               role: {id, parameters, resources}, grants: []}

        NB : contrairement à une version précédente, le rôle doit être
        imbriqué dans un objet "role" (pas un simple champ "roleId" à
        plat), et un champ "grants" (vide par défaut) est requis.

        Paramètres
        ----------
        database_id : str
        email : str
        name : str
        role_id : str
        role_parameters : dict, optionnel
            Paramètres de rôle (ex. restriction par partenaire)
        role_resources : List[str], optionnel
            Ressources auxquelles ce rôle s'applique
            (par défaut : [database_id], soit toute la base)
        locale : str
        """
        payload = {
            "email": email,
            "name": name,
            "locale": locale,
            "role": {
                "id": role_id,
                "parameters": role_parameters or {},
                "resources": role_resources or [database_id],
            },
            "grants": [],
        }
        data = self._post(f"/databases/{database_id}/users", json=payload)
        return DatabaseUser.from_dict(data)

    def delete_database_user(self, database_id: str,
                             user_id: int) -> None:
        """
        Retire un utilisateur d'une base de données.
        Équivalent R : deleteDatabaseUser() ->
        DELETE /resources/databases/{id}/users/{userId}
        """
        self._delete(f"/databases/{database_id}/users/{user_id}")

    def update_database_user_role(self, database_id: str,
                                  user_id: int,
                                  role_id: str,
                                  role_parameters: Dict[str, Any] = None,
                                  role_resources: List[str] = None) -> None:
        """
        Met à jour le rôle d'un utilisateur.
        Équivalent R : updateUserRole() ->
        POST /resources/databases/{id}/users/{userId}/role
        body: {assignments: [{id, parameters, resources}]}

        NB : contrairement à une version précédente (PUT avec
        {roleId} à plat), c'est un POST avec une liste "assignments".
        """
        payload = {
            "assignments": [{
                "id": role_id,
                "parameters": role_parameters or {},
                "resources": role_resources or [database_id],
            }]
        }
        self._post(f"/databases/{database_id}/users/{user_id}/role", json=payload)

    # ══════════════════════════════════════════════════════════════════════════
    # REQUÊTES / QUERIES
    # Équivalent R : queryTable() -> voir R/tableQuery.R
    # ══════════════════════════════════════════════════════════════════════════

    def query_columns(self, form_id: str, columns: Dict[str, str],
                      filter_expr: str = None,
                      sort: List[Dict[str, str]] = None,
                      window: List[int] = None,
                      truncate_strings: bool = True) -> dict:
        """
        Exécute une requête colonnaire brute sur un formulaire et
        retourne la réponse telle quelle (format "columnSet").
        Équivalent R : queryTable() (chemin avec colonnes explicites) ->
        POST /resources/query/columns

        Paramètres
        ----------
        form_id : str
        columns : dict
            {nom_de_colonne: expression}, ex. {"nom": "Name", "age": "AGE"}
        filter_expr : str, optionnel
            Formule ActivityInfo filtrant les enregistrements
        sort : List[dict], optionnel
            [{"dir": "ASC"|"DESC", "field": "..."}]
        window : List[int], optionnel
            [offset, limite]
        truncate_strings : bool
        """
        payload: Dict[str, Any] = {
            "rowSources": [{"rootFormId": form_id}],
            "columns": [
                {"id": name, "expression": expr}
                for name, expr in columns.items()
            ],
            "truncateStrings": truncate_strings,
        }
        if filter_expr:
            payload["filter"] = filter_expr
        if sort:
            payload["sort"] = sort
        if window:
            payload["window"] = window

        return self._post("/query/columns", json=payload)

    def query_table(self, form_id: str, columns: Dict[str, str],
                    filter_expr: str = None,
                    sort: List[Dict[str, str]] = None,
                    window: List[int] = None) -> List[dict]:
        """
        Comme query_columns(), mais retourne directement une liste de
        lignes (dicts {nom_de_colonne: valeur}) plutôt que le format
        colonnaire brut de l'API.
        """
        result = self.query_columns(
            form_id, columns, filter_expr=filter_expr,
            sort=sort, window=window,
        )
        return self._column_set_to_rows(result)

    # ══════════════════════════════════════════════════════════════════════════
    # PIÈCES JOINTES
    # Équivalent R : getAttachment()
    # ══════════════════════════════════════════════════════════════════════════

    def get_attachment(self, form_id: str, record_id: str,
                       field_id: str, blob_id: str) -> bytes:
        """
        Télécharge une pièce jointe.
        Équivalent R : getAttachment() ->
        GET /resources/form/{formId}/record/{recordId}/field/{fieldId}/blob/{blobId}

        NB IMPORTANT (non résolu) : le code R ajoute un suffixe fixe
        "/signature.png" à cette URL pour toutes les pièces jointes,
        pas seulement les signatures :

            resources/form/{formId}/record/{recordId}/field/{fieldId}
                /blob/{blobId}/signature.png

        On ignore ici s'il s'agit d'un simple nom de fichier arbitraire
        toléré par le serveur (souvent le cas pour les téléchargements
        HTTP où le dernier segment ne sert qu'à l'affichage) ou d'un
        suffixe réellement obligatoire. Cette méthode n'ajoute PAS ce
        suffixe. Si le téléchargement échoue avec une 404, essayez de
        rappeler l'endpoint en ajoutant "/signature.png" (ou un nom de
        fichier de votre choix) à la fin de l'URL.
        """
        url = (f"{self._base_url}{_RESOURCES_PREFIX}/form/{form_id}/record/"
               f"{record_id}/field/{field_id}/blob/{blob_id}")
        return safe_request_binary(self._session, "GET", url)

    # ══════════════════════════════════════════════════════════════════════════
    # JOBS ASYNCHRONES (exports, rapports, etc.)
    # Équivalent R : executeJob() dans R/extractLong.R
    # ══════════════════════════════════════════════════════════════════════════

    def get_job_status(self, job_id: str) -> dict:
        """
        Récupère le statut d'un job asynchrone.
        Équivalent R : GET /resources/jobs/{jobId}

        NB : les états observés dans le code R sont en minuscules
        ("started", "completed"), pas en majuscules. Toute autre
        valeur que "started"/"completed" est traitée comme un échec,
        avec le détail dans status["error"]["code"] / ["message"].
        """
        return self._get(f"/jobs/{job_id}")

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

            if state == "completed":
                logger.info(f"Job {job_id} terminé avec succès")
                return status
            elif state != "started":
                error = status.get("error", {}) or {}
                msg = error.get("message", "Échec inconnu")
                raise JobError(f"Job {job_id} échoué : {msg}", job_id)

            logger.debug(f"Job {job_id} en cours ({state})... "
                         f"{elapsed}s écoulées")
            time.sleep(poll_interval)
            elapsed += poll_interval

        raise JobError(
            f"Job {job_id} : délai maximum de {max_wait}s dépassé",
            job_id
        )

    def execute_job(self, job_type: str, descriptor: dict,
                    poll_interval: int = 2, max_wait: int = 300,
                    locale: str = "en") -> dict:
        """
        Lance un job asynchrone générique et attend sa complétion.
        Équivalent R : executeJob() ->
        POST /resources/jobs body {type, locale, descriptor}
        puis polling GET /resources/jobs/{id}

        Utilisé par exemple pour les exports de base de données
        (job_type="exportDatabaseForms" dans le package R).
        """
        job = self._post("/jobs", json={
            "type": job_type, "locale": locale, "descriptor": descriptor,
        })
        job_id = job.get("id")
        return self._wait_for_job(job_id, poll_interval=poll_interval,
                                   max_wait=max_wait)

    # ══════════════════════════════════════════════════════════════════════════
    # COMPTE
    # ══════════════════════════════════════════════════════════════════════════

    def get_account_status(self) -> dict:
        """
        Récupère le statut du compte utilisateur actuel.

        """
        return self._get("/account/status")

    def __repr__(self):
        return f"ActivityInfoClient(server={self._base_url!r})"
