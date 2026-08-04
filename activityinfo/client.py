"""
activityinfo.client
~~~~~~~~~~~~~~~~~~~
Client principal ActivityInfo Python.
Inspiré du package R bedatadriven/activityinfo-R.

Usage :
    from activityinfo import ActivityInfoClient
    client = ActivityInfoClient("votre_token")
    databases = client.get_databases()

IMPORTANT — Fiabilité des endpoints
------------------------------------
Ce client a été réécrit en comparant son comportement à celui du package R
officiel bedatadriven/activityinfo-R (qui parle à la même API REST), car la
version précédente utilisait un préfixe d'URL incorrect (`/api/...` au lieu
de `/resources/...`) et plusieurs endpoints inventés qui ne correspondent à
rien de réel côté serveur.

Les méthodes ci-dessous sont classées par niveau de confiance :

- HAUTE CONFIANCE : la structure de la requête et de la réponse a été
  confirmée en lisant le code source du package R correspondant.
- BEST-EFFORT (non testé en direct) : reconstruit fidèlement à partir du
  code R, mais jamais exécuté contre un vrai serveur ActivityInfo depuis cet
  environnement. À tester prudemment (petit volume de données) avant tout
  usage en production : import_records/import_dataframe, add_form,
  get_records/to_dataframe/query_table (reconstruction du format colonnes),
  get_form_geojson (existence de l'endpoint non confirmée).
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
    # Toutes les routes de l'API REST ActivityInfo vivent sous /resources/...
    # (et non /api/... comme la version précédente le supposait à tort).

    def _get(self, path: str, **kwargs) -> Any:
        return safe_request(self._session, "GET",
                            f"{self._base_url}/resources{path}", **kwargs)

    def _post(self, path: str, json: dict = None, **kwargs) -> Any:
        return safe_request(self._session, "POST",
                            f"{self._base_url}/resources{path}", json=json, **kwargs)

    def _delete(self, path: str, **kwargs) -> Any:
        return safe_request(self._session, "DELETE",
                            f"{self._base_url}/resources{path}", **kwargs)

    # ─── PING ──────────────────────────────────────────────────────────────────

    def ping(self) -> bool:
        """
        Vérifie la connexion au serveur ActivityInfo.

        NB : il n'existe pas d'endpoint /ping dédié dans l'API réelle (aucune
        trace dans le package R de référence). On teste donc la connectivité
        et l'authentification avec un appel réel et bon marché
        (`GET /resources/databases`) plutôt que de taper dans le vide.
        """
        try:
            self._get("/databases")
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
        Équivalent R : getDatabases()  →  GET /resources/databases

        Retourne
        --------
        List[Database]
        """
        data = self._get("/databases")
        return [Database.from_dict(d) for d in data]

    def get_database(self, database_id: str) -> Database:
        """
        Récupère l'arbre complet d'une base de données (y compris ses
        ressources : formulaires, dossiers...).
        Équivalent R : getDatabaseTree()  →  GET /resources/databases/{id}
        """
        data = self._get(f"/databases/{database_id}")
        return Database.from_dict(data)

    def get_database_resources(self, database_id: str
                                ) -> List[DatabaseResource]:
        """
        Liste toutes les ressources d'une base (formulaires, dossiers...).
        Équivalent R : getDatabaseResources()

        NB : il n'existe pas d'endpoint dédié /databases/{id}/resources
        dans l'API réelle. Les ressources sont un champ ("resources") de
        l'arbre renvoyé par GET /resources/databases/{id} — on récupère
        donc l'arbre complet et on en extrait ce champ.

        Retourne
        --------
        List[DatabaseResource]
        """
        data = self._get(f"/databases/{database_id}")
        resources = data.get("resources", [])
        return [DatabaseResource.from_dict(r) for r in resources]

    def add_database(self, label: str,
                     description: str = None,
                     database_id: str = None) -> Database:
        """
        Crée une nouvelle base de données.
        Équivalent R : addDatabase()  →  POST /resources/databases

        Paramètres
        ----------
        label : str
        description : str, optionnel
        database_id : str, optionnel
            Identifiant personnalisé ; un CUID est généré si non fourni
            (comme le fait le package R).
        """
        payload = {
            "id": database_id or generate_cuid(),
            "label": label,
            "templateId": "blank",
        }
        if description:
            payload["description"] = description
        data = self._post("/databases", json=payload)
        return Database.from_dict(data)

    def delete_database(self, database_id: str) -> None:
        """Supprime une base de données. DELETE /resources/databases/{id}"""
        self._delete(f"/databases/{database_id}")
        logger.info(f"Base supprimée : {database_id}")

    # ══════════════════════════════════════════════════════════════════════════
    # FORMULAIRES
    # Équivalent R : getFormSchema(), addForm(), updateFormSchema()
    # ══════════════════════════════════════════════════════════════════════════

    def get_form_schema(self, form_id: str) -> FormSchema:
        """
        Récupère le schéma complet d'un formulaire.
        Équivalent R : getFormSchema()  →  GET /resources/form/{id}/schema

        Paramètres
        ----------
        form_id : str
            ID du formulaire (visible dans l'URL du navigateur après "form/")
        """
        data = self._get(f"/form/{form_id}/schema")
        return FormSchema.from_dict(data)

    def add_form(self, database_id: str, label: str,
                 elements: List[dict],
                 folder_id: str = None,
                 description: str = None) -> FormSchema:
        """
        Crée un nouveau formulaire dans une base de données.
        Équivalent R : addForm()  →  POST /resources/databases/{id}/forms

        BEST-EFFORT : reconstruit fidèlement à partir du code source R
        (payload imbriqué formResource/formClass, réponse imbriquée sous
        forms[i].schema), mais jamais testé en direct depuis cet
        environnement. Teste d'abord avec un formulaire simple avant un
        usage en production.

        Paramètres
        ----------
        database_id : str
        label : str
        elements : List[dict]
            Liste de champs créés avec text_field(), quantity_field(), etc.
        folder_id : str, optionnel
            ID du dossier parent (par défaut, la base elle-même)
        description : str, optionnel
        """
        form_id = generate_cuid()
        parent_id = folder_id or database_id

        form_class: Dict[str, Any] = {
            "id": form_id,
            "databaseId": database_id,
            "label": label,
            "elements": elements,
        }
        if description:
            form_class["description"] = description

        request = {
            "formResource": {
                "id": form_id,
                "parentId": parent_id,
                "type": "FORM",
                "label": label,
                "visibility": "PRIVATE",
            },
            "formClass": form_class,
        }

        result = self._post(f"/databases/{database_id}/forms", json=request)

        forms = result.get("forms", [])
        match = next((f for f in forms if f.get("id") == form_id), None)
        if match is None or "schema" not in match:
            raise ActivityInfoError(
                f"Le serveur n'a pas renvoyé le schéma attendu pour le "
                f"formulaire {form_id} après sa création. Réponse : {result}"
            )
        return FormSchema.from_dict(match["schema"])

    def update_form_schema(self, schema: FormSchema) -> FormSchema:
        """
        Met à jour le schéma d'un formulaire existant.
        Équivalent R : updateFormSchema()  →  POST /resources/form/{id}/schema

        NB : c'est un POST, pas un PUT (contrairement à la version
        précédente de ce client) — l'API réelle attend un POST et renvoie
        le schéma imbriqué sous forms[0].schema.
        """
        result = self._post(f"/form/{schema.id}/schema", json=schema.to_dict())
        forms = result.get("forms", [])
        if not forms or "schema" not in forms[0]:
            raise ActivityInfoError(
                f"Le serveur n'a pas renvoyé le schéma attendu après la "
                f"mise à jour du formulaire {schema.id}. Réponse : {result}"
            )
        return FormSchema.from_dict(forms[0]["schema"])

    def add_field(self, form_id: str, field_dict: dict,
                 upload: bool = True) -> FormSchema:
        """
        Ajoute un nouveau champ à un formulaire existant.
        Équivalent R : addFormField()

        Récupère le schéma actuel, ajoute le champ à la liste, puis envoie
        le schéma complet mis à jour (via update_form_schema()) — il n'y a
        pas d'endpoint pour ajouter un seul champ isolément, l'API réelle
        attend toujours le schéma entier.

        Comme le fait R : si l'id ou le code du nouveau champ entre en
        collision avec un champ déjà présent dans le formulaire, un
        nouvel id/code est généré automatiquement (avec un avertissement
        dans les logs) plutôt que d'envoyer un schéma invalide au serveur.

        Paramètres
        ----------
        form_id : str
        field_dict : dict
            Un champ créé avec text_field(), quantity_field(), etc.
        upload : bool
            Si True (défaut), envoie la mise à jour au serveur et renvoie
            le schéma confirmé par le serveur. Si False, renvoie le schéma
            local mis à jour sans rien envoyer (pratique pour composer
            plusieurs ajouts avant un seul appel réseau — enchaîne alors
            avec client.update_form_schema(schema) toi-même).

        Exemple
        -------
        >>> from activityinfo import text_field
        >>> client.add_field("form001", text_field("Commentaire", code="COMMENT"))
        """
        schema = self.get_form_schema(form_id)
        existing_ids = {f.id for f in schema.fields}
        existing_codes = {f.code for f in schema.fields if f.code}

        field_dict = dict(field_dict)  # copie : ne pas muter l'original de l'appelant

        if field_dict.get("id") in existing_ids:
            old_id = field_dict["id"]
            field_dict["id"] = generate_cuid()
            logger.warning(
                f"add_field : id {old_id!r} déjà utilisé dans le formulaire "
                f"{form_id}, nouvel id généré automatiquement : "
                f"{field_dict['id']!r}"
            )

        code = field_dict.get("code")
        if code and code in existing_codes:
            new_code, i = code, 2
            while new_code in existing_codes:
                new_code = f"{code}_{i}"
                i += 1
            logger.warning(
                f"add_field : code {code!r} déjà utilisé dans le formulaire "
                f"{form_id}, nouveau code généré automatiquement : "
                f"{new_code!r}"
            )
            field_dict["code"] = new_code

        schema.fields.append(Field.from_dict(field_dict))

        if upload:
            return self.update_form_schema(schema)
        return schema

    def delete_form(self, database_id: str, form_id: str) -> None:
        """
        Supprime un formulaire.
        Équivalent R : deleteForm()  →  POST /resources/databases/{id}
        avec un diff de type resourceDeletions.

        Changement de signature par rapport à la version précédente :
        database_id est désormais requis, car l'API réelle exprime la
        suppression d'un formulaire comme une mise à jour de la base de
        données qui le contient (il n'existe pas de DELETE /form/{id}).
        """
        request = self._database_updates(resourceDeletions=[form_id])
        self._post(f"/databases/{database_id}", json=request)
        logger.info(f"Formulaire supprimé : {form_id} (base {database_id})")

    @staticmethod
    def _database_updates(**overrides) -> Dict[str, Any]:
        """
        Construit un diff vide de type "mise à jour de base de données",
        dans lequel on ne remplit que les clés pertinentes.
        Équivalent R : databaseUpdates()
        """
        base = {
            "resourceUpdates": [],
            "resourceDeletions": [],
            "lockUpdates": [],
            "lockDeletions": [],
            "roleUpdates": [],
            "roleDeletions": [],
            "languageUpdates": [],
            "languageDeletions": [],
            "originalLanguage": None,
            "continousTranslation": None,
            "translationFromDbMemory": None,
            "thirdPartyTranslation": None,
            "publishedTemplate": None,
        }
        base.update(overrides)
        return base

    # ══════════════════════════════════════════════════════════════════════════
    # ENREGISTREMENTS
    # Équivalent R : getRecords(), addRecord(), updateRecord(),
    #               deleteRecord(), recoverRecord(), importRecords()
    # ══════════════════════════════════════════════════════════════════════════

    def get_records(self, form_id: str,
                    fields: List[str] = None,
                    window_size: int = 5000) -> List[FormRecord]:
        """
        Récupère tous les enregistrements d'un formulaire.

         BEST-EFFORT : il n'existe PAS d'endpoint REST direct
        "liste des enregistrements d'un formulaire" dans l'API réelle
        (contrairement à ce que la version précédente supposait, avec
        pagination par curseur inventée). La vraie méthode consiste à
        interroger le formulaire via le mécanisme de requêtes en colonnes
        (POST /resources/query/columns), comme le fait queryTable() côté R,
        puis à reconstituer des lignes à partir des colonnes retournées.

        Cette reconstruction a été faite à partir du code source R mais
        n'a jamais été testée contre un vrai serveur — vérifie le résultat
        sur un petit formulaire avant de t'y fier pour un usage critique.

        Paramètres
        ----------
        form_id : str
        fields : List[str], optionnel
            Liste de codes de champs à inclure (tous les champs du schéma
            si None)
        window_size : int
            Taille des pages de résultats demandées au serveur.
        """
        if fields is None:
            schema = self.get_form_schema(form_id)
            fields = [f.code or f.id for f in schema.fields]

        columns = [
            {"id": "_id", "expression": "_id"},
            {"id": "_lastEditTime", "expression": "_lastEditTime"},
        ] + [{"id": f, "expression": f} for f in fields]

        all_records: List[FormRecord] = []
        offset = 0

        while True:
            payload = {
                "rowSources": [{"rootFormId": form_id}],
                "columns": columns,
                "truncateStrings": False,
                "window": [offset, window_size],
            }
            data = self._post("/query/columns", json=payload)
            rows = data.get("rows", 0)
            total_rows = data.get("totalRows", rows)
            col_values = self._parse_column_set(data, rows)

            for i in range(rows):
                record_id = col_values.get("_id", [None] * rows)[i]
                last_edit_time = col_values.get("_lastEditTime", [None] * rows)[i]
                values = {f: col_values.get(f, [None] * rows)[i] for f in fields}
                all_records.append(FormRecord(
                    record_id=record_id,
                    form_id=form_id,
                    values=values,
                    last_edit_time=last_edit_time,
                ))

            offset += rows
            if rows == 0 or offset >= total_rows:
                break

        logger.info(f"{len(all_records)} enregistrements récupérés "
                    f"depuis {form_id}")
        return all_records

    @staticmethod
    def _parse_column_set(data: dict, rows: int) -> Dict[str, List[Any]]:
        """
        Reconstitue, pour chaque colonne demandée, une liste de `rows`
        valeurs à partir de la réponse de /resources/query/columns.
        Adapté de parseColumnSet() côté R, qui gère 3 modes de stockage
        possibles pour une colonne : "constant" (une seule valeur répétée),
        "array" (une valeur par ligne), "empty" (colonne vide).
        """
        result: Dict[str, List[Any]] = {}
        for column in data.get("columns", []):
            col_id = column.get("id")
            storage = column.get("storage")
            if storage == "constant":
                result[col_id] = [column.get("value")] * rows
            elif storage == "array":
                values = column.get("values", [])
                result[col_id] = list(values) if len(values) == rows else \
                    (list(values) + [None] * (rows - len(values)))
            else:  # "empty" ou mode inconnu → colonne vide
                result[col_id] = [None] * rows
        return result

    def get_record(self, form_id: str, record_id: str) -> FormRecord:
        """
        Récupère un enregistrement unique.
        Équivalent R : getRecord()  →  GET /resources/form/{id}/record/{id}
        """
        data = self._get(f"/form/{form_id}/record/{record_id}")
        return FormRecord.from_dict(data, form_id)

    def add_record(self, form_id: str,
                   field_values: Dict[str, Any],
                   parent_record_id: str = None) -> FormRecord:
        """
        Ajoute un nouvel enregistrement.
        Équivalent R : addRecord()  →  POST /resources/update

        Paramètres
        ----------
        form_id : str
        field_values : dict
            Dictionnaire {code_champ: valeur}
        parent_record_id : str, optionnel
            Requis si `form_id` est un sous-formulaire.

        Exemple
        -------
        >>> client.add_record("cxy123", {
        ...     "NAME": "Alice Jones",
        ...     "AGE": 32,
        ...     "DATE": "2024-01-15"
        ... })
        """
        record_id = generate_cuid()
        change: Dict[str, Any] = {
            "recordId": record_id,
            "formId": form_id,
            "fields": field_values,
        }
        if parent_record_id:
            change["parentRecordId"] = parent_record_id

        self._post("/update", json={"changes": [change]})
        return self.get_record(form_id, record_id)

    def update_record(self, form_id: str, record_id: str,
                      field_values: Dict[str, Any]) -> FormRecord:
        """
        Met à jour un enregistrement existant.
        Équivalent R : updateRecord()  →  POST /resources/update
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
        Équivalent R : deleteRecord()  →  POST /resources/update
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
        Équivalent R : recoverRecord()
        →  POST /resources/form/{id}/record/{id}/recover
        """
        self._post(f"/form/{form_id}/record/{record_id}/recover")
        return self.get_record(form_id, record_id)

    def get_record_history(self, form_id: str,
                           record_id: str) -> List[dict]:
        """
        Récupère l'historique des modifications d'un enregistrement.
        Équivalent R : getRecordHistory()
        →  GET /resources/form/{id}/record/{id}/history
        """
        return self._get(f"/form/{form_id}/record/{record_id}/history")

    def import_records(self, form_id: str,
                       records: List[Dict[str, Any]],
                       wait: bool = True,
                       poll_interval: int = 2) -> dict:
        """
        Importe plusieurs enregistrements en masse (job asynchrone).
        Équivalent R : importRecords()

        BEST-EFFORT — RISQUE ÉLEVÉ, NON TESTÉ EN DIRECT.
        L'import réel en 3 étapes (mise en scène du fichier via
        POST /resources/imports/stage[/direct], upload du contenu au
        format "LINE DELIMITED JSON RECORDS" vers l'URL renvoyée, puis
        soumission d'un job "importRecords") a été reconstruit fidèlement
        à partir du code source R, mais n'a jamais pu être vérifié contre
        un vrai serveur depuis cet environnement (pas d'accès réseau à
        activityinfo.org ici). Teste d'abord avec 1 ou 2 lignes sur un
        formulaire de test avant tout usage en production.

        Paramètres
        ----------
        form_id : str
        records : List[dict]
            Liste de dictionnaires {code_champ: valeur}. Chaque dict peut
            optionnellement contenir une clé "_id" pour fixer l'id de
            l'enregistrement.
        wait : bool
            Attendre la fin du job (défaut : True)
        poll_interval : int
            Intervalle de polling en secondes (défaut : 2)
        """
        if not records:
            logger.warning("import_records : liste de records vide, rien à faire.")
            return {}

        field_ids = sorted({k for r in records for k in r.keys() if k != "_id"})

        lines = ["LINE DELIMITED JSON RECORDS", str(len(records)),
                 self._to_json_line(field_ids)]
        for r in records:
            record_id = r.get("_id") or generate_cuid()
            row = [record_id] + [r.get(f) for f in field_ids]
            lines.append(self._to_json_line(row))

        content = "\n".join(lines)

        stage = self._post("/imports/stage/direct")
        upload_url = stage.get("uploadUrl")
        import_id = stage.get("importId")
        if not upload_url or not import_id:
            raise ActivityInfoError(
                f"Réponse inattendue de /imports/stage/direct : {stage}"
            )
        if not upload_url.startswith("https://"):
            upload_url = f"{self._base_url}{upload_url}"

        upload_response = self._session.put(
            upload_url, data=content.encode("utf-8"),
            timeout=getattr(self._session, "_default_timeout", 30),
        )
        if upload_response.status_code not in (200, 201):
            raise ActivityInfoError(
                f"Échec de l'upload du fichier d'import vers {upload_url} "
                f"(status {upload_response.status_code})"
            )

        job_data = self._post("/jobs", json={
            "type": "importRecords",
            "locale": "en",
            "descriptor": {"formId": form_id, "importId": import_id},
        })
        job_id = job_data.get("id") or job_data.get("jobId")

        if wait and job_id:
            return self._wait_for_job(job_id, poll_interval)

        return job_data

    @staticmethod
    def _to_json_line(value) -> str:
        import json
        return json.dumps(value, ensure_ascii=False, separators=(",", ":"))

    # ── Import depuis pandas DataFrame ────────────────────────────────────────

    def import_dataframe(self, form_id: str, df,
                         field_mapping: Dict[str, str] = None,
                         wait: bool = True) -> dict:
        """
        Importe un DataFrame pandas dans un formulaire ActivityInfo.
        Bonus Python (pas d'équivalent direct en R).

        Voir les avertissements de import_records() : le mécanisme
        d'import réel n'a pas pu être testé en direct depuis cet
        environnement.

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

        # Convertir en liste de dicts, en remplaçant les NaN par None.
        # NB : on ne peut pas comparer au nom de classe "float" car
        # pandas/numpy retournent souvent des numpy.float64 ("float64"),
        # ce qui ratait silencieusement la détection des NaN. Le test
        # `v != v` est vrai uniquement pour NaN (IEEE 754), et fonctionne
        # aussi bien pour float, numpy.float64 ou pandas.NA sans avoir à
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
    #               deleteDatabaseUser(), updateUserRole()
    # ══════════════════════════════════════════════════════════════════════════

    def get_database_users(self, database_id: str) -> List[DatabaseUser]:
        """
        Liste les utilisateurs d'une base de données.
        Équivalent R : getDatabaseUsers()
        →  GET /resources/databases/{id}/users
        """
        data = self._get(f"/databases/{database_id}/users")
        users = data if isinstance(data, list) else data.get("users", [])
        return [DatabaseUser.from_dict(u) for u in users]

    def add_database_user(self, database_id: str, email: str,
                          name: str, role_id: str,
                          locale: str = "en",
                          role_parameters: Dict[str, Any] = None,
                          role_resources: List[str] = None) -> DatabaseUser:
        """
        Invite un utilisateur dans une base de données et lui assigne un rôle.
        Équivalent R : addDatabaseUser()
        →  POST /resources/databases/{id}/users

        NB : contrairement à la version précédente (qui envoyait un simple
        "roleId" au niveau racine), l'API réelle attend un objet "role"
        imbriqué {id, parameters, resources} ainsi qu'une clé "grants".

        Paramètres
        ----------
        role_id : str
            L'id du rôle à assigner (ex: "admin", ou l'id d'un rôle
            personnalisé de la base).
        role_parameters : dict, optionnel
            Valeurs des paramètres du rôle si celui-ci en définit.
        role_resources : list[str], optionnel
            Ressources auxquelles s'applique ce rôle (par défaut, la base
            de données elle-même).
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
        # La réponse peut être soit directement l'utilisateur créé, soit
        # {"added": true, "user": {...}} selon le cas (nouveau compte vs
        # compte existant) — on gère les deux.
        user_data = data.get("user", data) if isinstance(data, dict) else data
        return DatabaseUser.from_dict(user_data)

    def delete_database_user(self, database_id: str,
                             user_id: int) -> None:
        """
        Retire un utilisateur d'une base de données.
        Équivalent R : deleteDatabaseUser()
        →  DELETE /resources/databases/{id}/users/{user_id}
        """
        self._delete(f"/databases/{database_id}/users/{user_id}")

    def update_database_user_role(self, database_id: str,
                                  user_id: int,
                                  role_id: str,
                                  role_parameters: Dict[str, Any] = None,
                                  role_resources: List[str] = None) -> None:
        """
        Met à jour le rôle d'un utilisateur.
        Équivalent R : updateUserRole()
        →  POST /resources/databases/{id}/users/{user_id}/role

        NB : c'est un POST, pas un PUT, et le payload attend une liste
        "assignments" plutôt qu'un simple "roleId" (contrairement à la
        version précédente de ce client).
        """
        assignment = {
            "id": role_id,
            "parameters": role_parameters or {},
            "resources": role_resources or [database_id],
        }
        self._post(
            f"/databases/{database_id}/users/{user_id}/role",
            json={"assignments": [assignment]}
        )

    # ══════════════════════════════════════════════════════════════════════════
    # REQUÊTES / QUERIES
    # Équivalent R : queryTable(), queryColumns()
    # ══════════════════════════════════════════════════════════════════════════

    def query_table(self, form_id: str,
                    columns: List[str] = None,
                    filter_expr: str = None) -> List[dict]:
        """
        Exécute une requête sur un formulaire et retourne des lignes
        (une liste de dicts {nom_colonne: valeur}).
        Équivalent R : queryTable()

        NB : la version précédente postait vers `/query/rows`, un chemin
        qui n'existe pas dans l'API réelle. Le bon endpoint est
        POST /resources/query/columns (réponse au format colonnes,
        reconstituée ici en lignes).

        La reconstruction ligne-par-ligne à partir de la réponse
        colonnes n'a pas pu être testée en direct — voir get_records()
        pour les mêmes réserves.
        """
        if not columns:
            raise ValidationError(
                "query_table nécessite une liste de colonnes explicite "
                "(utilise get_records() pour récupérer tous les champs "
                "d'un formulaire)."
            )

        payload: Dict[str, Any] = {
            "rowSources": [{"rootFormId": form_id}],
            "columns": [{"id": c, "expression": c} for c in columns],
            "truncateStrings": True,
        }
        if filter_expr:
            payload["filter"] = filter_expr

        data = self._post("/query/columns", json=payload)
        rows = data.get("rows", 0)
        col_values = self._parse_column_set(data, rows)
        return [
            {c: col_values.get(c, [None] * rows)[i] for c in columns}
            for i in range(rows)
        ]

    def query_columns(self, form_id: str,
                      columns: Dict[str, str]) -> dict:
        """
        Requête par colonnes (format analytique brut, non reconstitué en
        lignes). Équivalent R : queryTable() en mode colonnes.
        →  POST /resources/query/columns

        Paramètres
        ----------
        columns : dict
            {nom_de_sortie: expression_activityinfo}, par exemple
            {"nom": "NAME", "age": "AGE"}.

        Retourne
        --------
        dict brut renvoyé par le serveur (colonnes + métadonnées de
        pagination : rows, offset, totalRows).
        """
        payload = {
            "rowSources": [{"rootFormId": form_id}],
            "columns": [{"id": k, "expression": v} for k, v in columns.items()],
        }
        return self._post("/query/columns", json=payload)

    # ══════════════════════════════════════════════════════════════════════════
    # PIÈCES JOINTES
    # Équivalent R : getAttachment()
    # ══════════════════════════════════════════════════════════════════════════

    def get_attachment(self, form_id: str, record_id: str,
                       field_id: str, blob_id: str) -> bytes:
        """
        Télécharge une pièce jointe.
        Équivalent R : getAttachment()
        →  GET /resources/form/{id}/record/{id}/field/{id}/blob/{id}
        """
        url = (f"{self._base_url}/resources/form/{form_id}/record/"
               f"{record_id}/field/{field_id}/blob/{blob_id}")
        return safe_request_binary(self._session, "GET", url)

    def get_form_geojson(self, form_id: str) -> dict:
        """
        Récupère les données géographiques d'un formulaire en GeoJSON.

        NON CONFIRMÉ : aucune trace de cet endpoint (sous quelque
        forme que ce soit) dans le package R de référence. Il est
        possible qu'il n'existe pas, ou pas sous ce chemin. Utilisation
        à tes risques — signale-moi le résultat (succès ou 404) pour
        qu'on corrige si besoin.
        """
        return self._get(f"/form/{form_id}/geo")

    # ══════════════════════════════════════════════════════════════════════════
    # JOBS ASYNCHRONES
    # ══════════════════════════════════════════════════════════════════════════

    def get_job_status(self, job_id: str) -> dict:
        """Récupère le statut d'un job asynchrone. GET /resources/jobs/{id}"""
        return self._get(f"/jobs/{job_id}")

    def _wait_for_job(self, job_id: str,
                      poll_interval: int = 2,
                      max_wait: int = 300) -> dict:
        """
        Attend la fin d'un job asynchrone avec polling.
        Lève JobError si le job échoue ou dépasse max_wait secondes.

        NB : l'API réelle utilise des états en minuscules ("started",
        "completed"), pas "RUNNING"/"COMPLETED"/"FAILED" en majuscules
        comme le supposait la version précédente — ce qui la faisait
        boucler indéfiniment (jusqu'à max_wait) même en cas de succès.
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
                msg = error.get("message", f"État inattendu : {state!r}")
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
        """
        Récupère le statut du compte utilisateur actuel.

        NON DISPONIBLE : aucun endpoint équivalent trouvé dans le
        package R de référence. Plutôt que de renvoyer silencieusement
        des données incorrectes (comportement précédent), cette méthode
        lève explicitement une erreur.
        """
        raise NotImplementedError(
            "get_account_status() n'a pas d'endpoint confirmé dans l'API "
            "ActivityInfo réelle. Si tu connais le bon endpoint, ouvre une "
            "issue ou contacte support@activityinfo.org pour confirmation."
        )

    def __repr__(self):
        return f"ActivityInfoClient(server={self._base_url!r})"
