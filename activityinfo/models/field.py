"""
activityinfo.models.field
~~~~~~~~~~~~~~~~~~~~~~~~~
Modèles pour les champs de formulaires ActivityInfo.
Inspiré de fieldSchema() du package R bedatadriven.

"""

from dataclasses import dataclass, field
from typing import Optional, List, Any, Dict, Literal

# Types de champs réellement renvoyés par l'API ActivityInfo (voir note
# ci-dessus sur l'incohérence de casse — c'est le comportement réel du
# serveur, pas une coquille de notre part).
FIELD_TYPES = Literal[
    "FREE_TEXT",
    "NARRATIVE",
    "quantity",
    "date",
    "month",
    "epiweek",
    "fortnight",
    "enumerated",
    "reference",
    "attachment",
    "geopoint",
    "calculated",
    "serial",
    "section",
    "subform",
]


@dataclass
class FieldOption:
    """Option pour un champ "enumerated" (sélection simple ou multiple)."""
    id: str
    label: str
    code: Optional[str] = None

    def to_dict(self) -> dict:
        d = {"id": self.id, "label": self.label}
        if self.code:
            d["code"] = self.code
        return d

    @classmethod
    def from_dict(cls, data: dict) -> "FieldOption":
        return cls(
            id=data["id"],
            label=data.get("label", ""),
            code=data.get("code"),
        )


@dataclass
class Field:
    """
    Représente un champ de formulaire ActivityInfo.

    Équivalent de fieldSchema() dans le package R.
    """
    id: str
    label: str
    type: str
    code: Optional[str] = None
    description: Optional[str] = None
    required: bool = False
    key: bool = False
    relevance_rule: Optional[str] = None
    validation_rule: Optional[str] = None

    # Pour "enumerated" (sélection simple ou multiple)
    options: List[FieldOption] = field(default_factory=list)
    cardinality: Optional[str] = None  # "single" ou "multiple"

    # Pour "reference"
    reference_form_id: Optional[str] = None

    # Pour "subform" (champ intégrant directement un sous-formulaire)
    subform_id: Optional[str] = None

    # Pour "quantity"
    units: Optional[str] = None
    aggregation: Optional[str] = None

    # Pour "calculated"
    formula: Optional[str] = None

    # Données brutes de l'API — toujours disponibles même pour les types
    # de champs non spécifiquement modélisés ci-dessus (section, subform,
    # attachment, geopoint...).
    _raw: Dict[str, Any] = field(default_factory=dict, repr=False)

    def to_dict(self) -> dict:
        """Sérialise le champ pour l'API ActivityInfo."""
        d: Dict[str, Any] = {
            "id": self.id,
            "label": self.label,
            "type": self.type,
            "required": self.required,
            "key": self.key,
        }
        if self.code:
            d["code"] = self.code
        if self.description:
            d["description"] = self.description
        if self.relevance_rule:
            d["relevanceCondition"] = self.relevance_rule
        if self.validation_rule:
            d["validationCondition"] = self.validation_rule

        # Un seul de ces attributs est pertinent à la fois selon le type
        # du champ. On utilise une chaîne elif pour ne jamais écraser
        # silencieusement typeParameters si plusieurs attributs se
        # trouvaient renseignés simultanément.
        if self.options:
            d["typeParameters"] = {
                "cardinality": self.cardinality or "single",
                "presentation": "automatic",
                "values": [o.to_dict() for o in self.options],
            }
        elif self.reference_form_id:
            d["typeParameters"] = {
                "cardinality": "single",
                "range": [{"formId": self.reference_form_id}],
            }
        elif self.subform_id:
            d["typeParameters"] = {"formId": self.subform_id}
        elif self.units is not None:
            d["typeParameters"] = {
                "units": self.units,
                "aggregation": self.aggregation or "SUM",
            }
        elif self.formula:
            d["typeParameters"] = {"formula": self.formula}

        return d

    @classmethod
    def from_dict(cls, data: dict) -> "Field":
        """Crée un Field depuis la réponse JSON de l'API."""
        type_params = data.get("typeParameters", {}) or {}
        options = []
        cardinality = None
        reference_form_id = None
        subform_id = None
        units = None
        aggregation = None
        formula = None

        field_type = data.get("type", "FREE_TEXT")

        if field_type == "enumerated":
            options = [
                FieldOption.from_dict(v)
                for v in type_params.get("values", [])
            ]
            cardinality = type_params.get("cardinality")
        elif field_type == "reference":
            ranges = type_params.get("range", [])
            if ranges:
                reference_form_id = ranges[0].get("formId")
        elif field_type == "subform":
            subform_id = type_params.get("formId")
        elif field_type == "quantity":
            units = type_params.get("units")
            aggregation = type_params.get("aggregation")
        elif field_type == "calculated":
            formula = type_params.get("formula")
        # "section", "subform", "geopoint", "attachment", "date", "month",
        # "epiweek", "fortnight", "serial", "FREE_TEXT", "NARRATIVE" n'ont
        # pas d'attribut dédié ci-dessus : leurs typeParameters restent
        # accessibles via `._raw` si besoin.

        return cls(
            id=data["id"],
            label=data.get("label", ""),
            type=field_type,
            code=data.get("code"),
            description=data.get("description"),
            required=data.get("required", False),
            key=data.get("key", False),
            relevance_rule=data.get("relevanceCondition"),
            validation_rule=data.get("validationCondition"),
            options=options,
            cardinality=cardinality,
            reference_form_id=reference_form_id,
            subform_id=subform_id,
            units=units,
            aggregation=aggregation,
            formula=formula,
            _raw=data,
        )

    @property
    def is_section(self) -> bool:
        """True si ce champ est en fait un en-tête de section (élément de
        mise en page, sans valeur de donnée associée)."""
        return self.type == "section"

    def __repr__(self):
        return f"Field(id={self.id!r}, label={self.label!r}, type={self.type!r})"


# ─── Fonctions de création de champs (calquées sur le package R) ───────────────
# NB : les chaînes de type ci-dessous ("quantity", "date", "enumerated",
# "reference", "geopoint"...) sont volontairement en minuscules — c'est ce
# que l'API réelle attend, malgré l'incohérence avec FREE_TEXT/NARRATIVE.

def text_field(label: str, code: str = None, description: str = None,
               required: bool = False, key: bool = False,
               barcode: bool = False) -> dict:
    """Crée un champ texte libre. Équivalent de textFieldSchema() en R."""
    from ..utils.cuid import generate_cuid
    d = {"id": generate_cuid(), "label": label, "type": "FREE_TEXT",
         "required": required, "key": key}
    if code: d["code"] = code
    if description: d["description"] = description
    if barcode: d["typeParameters"] = {"barcode": True}
    return d


def narrative_field(label: str, code: str = None,
                    required: bool = False) -> dict:
    """Crée un champ texte long (narratif)."""
    from ..utils.cuid import generate_cuid
    return {"id": generate_cuid(), "label": label, "type": "NARRATIVE",
            "required": required, "code": code}


def quantity_field(label: str, code: str = None, units: str = "",
                   aggregation: str = "SUM",
                   required: bool = False) -> dict:
    """Crée un champ numérique. Équivalent de quantityFieldSchema() en R."""
    from ..utils.cuid import generate_cuid
    d = {"id": generate_cuid(), "label": label, "type": "quantity",
         "required": required,
         "typeParameters": {"units": units, "aggregation": aggregation}}
    if code: d["code"] = code
    return d


def date_field(label: str, code: str = None, required: bool = False) -> dict:
    """Crée un champ date."""
    from ..utils.cuid import generate_cuid
    d = {"id": generate_cuid(), "label": label, "type": "date",
         "required": required}
    if code: d["code"] = code
    return d


def month_field(label: str, code: str = None, required: bool = False) -> dict:
    """Crée un champ mois (format YYYY-MM)."""
    from ..utils.cuid import generate_cuid
    d = {"id": generate_cuid(), "label": label, "type": "month",
         "required": required}
    if code: d["code"] = code
    return d


def single_select_field(label: str, options: List[str], code: str = None,
                         required: bool = False,
                         relevance_rule: str = None) -> dict:
    """
    Crée un champ sélection unique.
    Équivalent de singleSelectFieldSchema() en R — type réel "enumerated"
    avec typeParameters.cardinality = "single".
    """
    from ..utils.cuid import generate_cuid
    values = [{"id": generate_cuid(), "label": opt} for opt in options]
    d = {
        "id": generate_cuid(), "label": label,
        "type": "enumerated", "required": required,
        "typeParameters": {
            "cardinality": "single",
            "presentation": "automatic",
            "values": values,
        },
    }
    if code: d["code"] = code
    if relevance_rule: d["relevanceCondition"] = relevance_rule
    return d


def multi_select_field(label: str, options: List[str], code: str = None,
                        required: bool = False) -> dict:
    """Crée un champ sélection multiple — type réel "enumerated" avec
    typeParameters.cardinality = "multiple"."""
    from ..utils.cuid import generate_cuid
    values = [{"id": generate_cuid(), "label": opt} for opt in options]
    d = {
        "id": generate_cuid(), "label": label,
        "type": "enumerated", "required": required,
        "typeParameters": {
            "cardinality": "multiple",
            "presentation": "automatic",
            "values": values,
        },
    }
    if code: d["code"] = code
    return d


def reference_field(label: str, form_id: str, code: str = None,
                    required: bool = False) -> dict:
    """Crée un champ référence vers un autre formulaire."""
    from ..utils.cuid import generate_cuid
    d = {
        "id": generate_cuid(), "label": label,
        "type": "reference", "required": required,
        "typeParameters": {
            "cardinality": "single",
            "range": [{"formId": form_id}],
        },
    }
    if code: d["code"] = code
    return d


def geopoint_field(label: str, code: str = None,
                   required: bool = False,
                   manual_entry_allowed: bool = True) -> dict:
    """Crée un champ géolocalisation (latitude/longitude)."""
    from ..utils.cuid import generate_cuid
    d = {"id": generate_cuid(), "label": label, "type": "geopoint",
         "required": required,
         "typeParameters": {"manualEntryAllowed": manual_entry_allowed}}
    if code: d["code"] = code
    return d


def calculated_field(label: str, formula: str, code: str = None) -> dict:
    """Crée un champ calculé à partir d'une formule."""
    from ..utils.cuid import generate_cuid
    d = {"id": generate_cuid(), "label": label, "type": "calculated",
         "typeParameters": {"formula": formula}}
    if code: d["code"] = code
    return d


def section_field(label: str, indentation_level: int = 1) -> dict:
    """Crée un en-tête de section (élément de mise en page uniquement,
    ne stocke aucune valeur)."""
    from ..utils.cuid import generate_cuid
    return {
        "id": generate_cuid(), "label": label, "type": "section",
        "typeParameters": {"indentationLevel": indentation_level},
    }
