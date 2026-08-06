# activityinfo-python

Package Python complet pour l'API [ActivityInfo](https://www.activityinfo.org/),
inspiré du package R officiel [bedatadriven/activityinfo-R](https://github.com/bedatadriven/activityinfo-R).

## Niveaux de confiance

Ce package a été construit puis largement corrigé en comparant son comportement
à celui du package R officiel (qui parle à la même API REST) et en le testant
contre un vrai serveur. Toutes les méthodes n'ont pas le même niveau de
certitude :

- **Haute confiance** (structure vérifiée dans le code source R **et**
  testée contre un vrai serveur) : `get_databases`, `get_database`,
  `get_database_resources`, `get_form_schema` (y compris sous-formulaires),
  `get_record`, `add_record`/`update_record`/`delete_record`,
  `recover_record`, `get_record_history`, `get_database_users`,
  `delete_database_user`, `get_job_status`, `get_attachment`, `add_field`,
  `delete_field`.
- **Best-effort** (reconstruit fidèlement à partir du code source R, mais
  jamais testé en direct contre un vrai serveur) : `add_form`,
  `import_records`/`import_dataframe` (le plus risqué — teste avec 1-2
  lignes d'abord), `get_records`/`to_dataframe`/`query_table` (reconstruction
  du format colonnes), `get_form_geojson` (existence même de l'endpoint non
  confirmée), `add_database_user`/`update_database_user_role` (payload rôle
  imbriqué), le positionnement `after=`/`position=` de `add_field`.

Teste toujours les fonctionnalités best-effort sur un formulaire non-critique
avant un usage réel, et vérifie après coup qu'aucun champ existant n'a été
perturbé (voir [Bonnes pratiques](#bonnes-pratiques-avant-une-écriture)).

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

# Ressources d'une base (formulaires, dossiers, sous-formulaires...)
# NB : il n'existe pas d'endpoint séparé pour ça — get_database_resources()
# lit le champ "resources" de l'arbre complet de la base.
resources = client.get_database_resources("db_id")
forms = [r for r in resources if r.is_form]
sub_forms = [r for r in resources if r.is_sub_form]  # type == "SUB_FORM"

# Créer une base
new_db = client.add_database("Enquête Flash 2025")
```

---

## Formulaires

### Types de champs réels

Le vocabulaire des types de champs de l'API a une casse volontairement
incohérente — ce n'est pas une coquille de notre part, c'est ainsi que le
serveur les renvoie réellement : `"FREE_TEXT"` et `"NARRATIVE"` restent en
majuscules, mais tous les autres types (`"quantity"`, `"date"`,
`"enumerated"`, `"reference"`, `"calculated"`, `"geopoint"`, `"section"`,
`"subform"`, `"serial"`, `"month"`...) sont en minuscules.

Il n'existe pas de type `SINGLE_SELECTION`/`MULTI_SELECTION` séparés : les
deux sont un seul type `"enumerated"`, différencié par
`typeParameters.cardinality` (`"single"` ou `"multiple"`).

```python
from activityinfo import (
    text_field, narrative_field, quantity_field, date_field, month_field,
    single_select_field, multi_select_field, reference_field, geopoint_field,
    calculated_field, section_field, subform_field,
)

# Lire le schéma
schema = client.get_form_schema("form_id")
print(schema.label, len(schema.fields), "champs")
for f in schema.fields:
    print(f.code or f.id, "-", f.type, "- is_section:", f.is_section)

# Créer un formulaire (best-effort, teste d'abord)
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

### Ajouter / supprimer un champ sur un formulaire existant

Il n'existe pas d'endpoint pour ajouter ou supprimer un seul champ isolément
— `add_field()`/`delete_field()` récupèrent le schéma complet, le modifient,
et renvoient le tout via `update_form_schema()`. Elles reproduisent les
mêmes garde-fous que le package R (`addFormField()`/`deleteFormField()`) :
collision d'id/code évitée automatiquement à l'ajout, ambiguïté de label
détectée à la suppression.

```python
# Ajouter un champ à la fin
client.add_field("form_id", text_field("Commentaire", code="COMMENT"))

# ... ou juste après un champ précis
client.add_field("form_id", text_field("Note", code="NOTE"), after="NOM")

# Supprimer par code, id, ou label (exactement un des trois)
client.delete_field("form_id", code="COMMENT")
```

### Règles de pertinence (afficher un champ sous condition)

La clé JSON réelle est `relevanceCondition` (le paramètre Python reste
`relevance_rule`, comme côté R). Exemple confirmé par la doc officielle R —
comparaison sur un champ du **même** formulaire :

```python
single_select_field(
    "Are you pregnant", ["Yes", "No"],
    relevance_rule="SEX != 'Male'"
)
```

Pour référencer un champ d'un formulaire **parent** depuis un sous-formulaire
(syntaxe confirmée dans le contexte des requêtes, probable mais non garantie
en `relevanceCondition` — à vérifier après test) :

```python
relevance_rule = "parent.CODE_DU_CHAMP_PARENT == 'Valeur'"
```

### Sous-formulaires

Un sous-formulaire est un formulaire normal dont le lien vers son parent est
renseigné à deux endroits (les deux sont gérés automatiquement par
`parent_form_id`) :

```python
# 1. Créer le sous-formulaire
sub_form = client.add_form(
    "db_id", "Détails",
    elements=[...],
    parent_form_id="ID_DU_FORMULAIRE_PARENT",
)

# 2. L'embarquer dans le formulaire parent, avec une condition d'affichage
client.add_field("ID_DU_FORMULAIRE_PARENT", subform_field(
    "Détails", subform_id=sub_form.id, code="DETAILS",
    relevance_rule="INCLUT_DETAILS == 'Oui'",
))
```

Un enregistrement de sous-formulaire nécessite `parent_record_id` :

```python
client.add_record(
    sub_form.id,
    {"CODE_CHAMP": "valeur"},
    parent_record_id="id_de_l_enregistrement_parent",
)
```

---

## Enregistrements

```python
# Lire tous les enregistrements d'un formulaire (best-effort — reconstruit
# via le mécanisme de requêtes en colonnes, il n'existe pas d'endpoint
# "liste paginée" direct dans l'API réelle)
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

Best-effort — voir la note sur `import_records()` plus haut. Teste avec
un petit volume avant tout usage réel.

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

# Ajouter un utilisateur (le rôle est un objet imbriqué côté API réelle,
# géré automatiquement par role_id/role_parameters/role_resources)
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
| `getDatabaseTree()`          | `client.get_database(db_id)`               |
| `getDatabaseResources()`     | `client.get_database_resources(db_id)`     |
| `getFormSchema()`            | `client.get_form_schema(form_id)`          |
| `addForm()`                  | `client.add_form(db_id, label, elements)`  |
| `updateFormSchema()`         | `client.update_form_schema(schema)`        |
| `addFormField()`             | `client.add_field(form_id, field_dict)`    |
| `deleteFormField()`          | `client.delete_field(form_id, code=...)`   |
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
| `updateUserRole()`           | `client.update_database_user_role(...)`    |
| `queryTable()`                | `client.query_table(form_id, columns)`    |
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

Si le serveur répond en HTML plutôt qu'en JSON (souvent le signe d'un token
invalide/expiré ou d'une mauvaise `server_url`), le message d'exception
l'indique clairement plutôt que d'afficher la page HTML brute.

---

## Bonnes pratiques avant une écriture

Pour toute méthode marquée **best-effort** ci-dessus, ou avant une écriture
sur un formulaire de production :

```python
# 1. État avant modification
schema = client.get_form_schema("form_id")
avant = {f.code or f.id for f in schema.fields}

# 2. La modification
updated = client.add_field("form_id", text_field("Test", code="TEST_TEMP"))

# 3. Vérifier qu'aucun champ existant n'a été perturbé
apres = {f.code or f.id for f in updated.fields}
print("Perdus :", avant - apres)    # doit être vide
print("Ajoutés :", apres - avant)   # doit contenir uniquement le nouveau champ
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
