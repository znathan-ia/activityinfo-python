# activityinfo-python

Package Python complet pour l'API [ActivityInfo](https://www.activityinfo.org/),
inspiré du package R officiel [bedatadriven/activityinfo-R](https://github.com/bedatadriven/activityinfo-R).

## Installation

```bash
pip install activityinfo
# Avec support pandas :
pip install activityinfo[pandas]
```

## Authentification

Générez un token sur ActivityInfo : **Profil > Paramètres > Tokens API**

```python
from activityinfo import ActivityInfoClient

client = ActivityInfoClient("votre_token_personnel")
```

Pour un serveur ActivityInfo Self-Managed :

```python
client = ActivityInfoClient(
    token="votre_token",
    server_url="https://votre-serveur.activityinfo.org"
)
```

---

## Bases de données

```python
# Lister toutes les bases accessibles
databases = client.get_databases()
for db in databases:
    print(db.id, db.label)

# Ressources d'une base (formulaires, dossiers...)
resources = client.get_database_resources("db_id")
forms = [r for r in resources if r.is_form]

# Créer une base
new_db = client.add_database("Enquête Flash 2025")
```

---

## Formulaires

```python
from activityinfo import (
    text_field, quantity_field,
    single_select_field, date_field, geopoint_field
)

# Lire le schéma
schema = client.get_form_schema("form_id")
print(schema.label, len(schema.fields), "champs")

# Créer un formulaire
new_form = client.add_form(
    database_id="db_id",
    label="Formulaire Bénéficiaires",
    elements=[
        text_field("Nom complet",   code="NOM",    required=True),
        text_field("Prénom",        code="PRENOM"),
        quantity_field("Age",       code="AGE",    units="ans"),
        single_select_field("Sexe", ["Homme", "Femme", "Autre"], code="SEXE"),
        date_field("Date d'entretien", code="DATE", required=True),
        geopoint_field("Localisation", code="GPS"),
    ]
)
```

---

## Enregistrements

```python
# Lire tous les enregistrements (pagination automatique)
records = client.get_records("form_id")

# Ajouter un enregistrement
record = client.add_record("form_id", {
    "NOM":    "Konaté",
    "PRENOM": "Ibrahim",
    "AGE":    34,
    "SEXE":   "Homme",
    "DATE":   "2025-03-14",
})

# Mettre à jour
client.update_record("form_id", record.record_id, {"AGE": 35})

# Supprimer
client.delete_record("form_id", record.record_id)

# Restaurer un enregistrement supprimé
client.recover_record("form_id", record.record_id)

# Historique des modifications
history = client.get_record_history("form_id", record.record_id)
```

---

## Intégration pandas

```python
# Exporter un formulaire en DataFrame
df = client.to_dataframe("form_id")
print(df.head())

# Importer un DataFrame entier
client.import_dataframe(
    form_id="form_id",
    df=df,
    field_mapping={
        "colonne_excel": "CODE_CHAMP_AI"
    }
)
```

---

## Gestion des utilisateurs

```python
# Lister les utilisateurs
users = client.get_database_users("db_id")

# Ajouter un utilisateur
client.add_database_user(
    database_id="db_id",
    email="agent@humanitaire.org",
    name="Agent Terrain",
    role_id="readonly",
    locale="fr"
)

# Supprimer un utilisateur
client.delete_database_user("db_id", user_id=123)

# Changer le rôle
client.update_database_user_role("db_id", user_id=123, role_id="admin")
```

---

## Correspondance avec le package R

| R (bedatadriven)             | Python (ce package)                        |
|------------------------------|--------------------------------------------|
| `activityInfoToken()`        | `ActivityInfoClient("token")`              |
| `getDatabases()`             | `client.get_databases()`                   |
| `getDatabaseResources()`     | `client.get_database_resources(db_id)`     |
| `getFormSchema()`            | `client.get_form_schema(form_id)`          |
| `addForm()`                  | `client.add_form(db_id, label, elements)`  |
| `getRecords() \|> collect()` | `client.get_records(form_id)`              |
| `addRecord()`                | `client.add_record(form_id, values)`       |
| `updateRecord()`             | `client.update_record(form_id, id, vals)`  |
| `deleteRecord()`             | `client.delete_record(form_id, id)`        |
| `recoverRecord()`            | `client.recover_record(form_id, id)`       |
| `importRecords()`            | `client.import_records(form_id, records)`  |
| `getRecordHistory()`         | `client.get_record_history(form_id, id)`   |
| `getDatabaseUsers()`         | `client.get_database_users(db_id)`         |
| `addDatabaseUser()`          | `client.add_database_user(...)`            |
| `deleteDatabaseUser()`       | `client.delete_database_user(db_id, uid)`  |
| *(pas d'équivalent)*         | `client.to_dataframe(form_id)`             |
| *(pas d'équivalent)*         | `client.import_dataframe(form_id, df)`     |

---

## Gestion des erreurs

```python
from activityinfo.exceptions import (
    AuthenticationError, NotFoundError,
    RateLimitError, JobError
)

try:
    records = client.get_records("form_id")
except AuthenticationError:
    print("Token invalide ou expiré")
except NotFoundError:
    print("Formulaire introuvable")
except RateLimitError:
    print("Quota API dépassé, réessayer plus tard")
```

---

## Tests

```bash
pip install pytest
pytest tests/ -v
```

---

## Licence

MIT
