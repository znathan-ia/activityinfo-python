"""
activityinfo.models.field
~~~~~~~~~~~~~~~~~~~~~~~~~
Modèles pour les champs de formulaires ActivityInfo.
Inspiré de fieldSchema() du package R bedatadriven.
"""

from dataclasses import dataclass, field
from typing import Optional, List, Any, Dict, Literal

# Types de champs supportés par ActivityInfo
FIELD_TYPES = Literal[
    "FREE_TEXT",
    "NARRATIVE",
    "QUANTITY",
    "DATE",
    "MONTH",
    "WEEK",
    "SINGLE_SELECTION",
    "MULTI_SELECTION",
    "REFERENCE",
    "ATTACHMENT",
    "IMAGE",
    "GEOPOINT",
    "CALCULATED",
    "SERIAL",
    "BARCODE",
    "USERNAME",
    "BOOLEAN",
]


@dataclass
class FieldOption:
    """Option pour les champs SINGLE_SELECTION / MULTI_SELECTION."""
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

    # Pour SINGLE_SELECTION / MULTI_SELECTION
    options: List[FieldOption] = field(default_factory=list)

    # Pour REFERENCE
    reference_form_id: Optional[str] = None

    # Pour QUANTITY
    units: Optional[str] = None

    # Pour CALCULATED
    formula: Optional[str] = None

    # Données brutes de l'API
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
            d["relevanceRule"] = self.relevance_rule
        if self.validation_rule:
            d["validationRule"] = self.validation_rule

        # Un seul de ces attributs est pertinent à la fois selon le type
        # du champ (options / référence / unités / formule). On utilise
        # une chaîne elif plutôt que des if indépendants pour ne jamais
        # écraser silencieusement typeParameters si plusieurs attributs
        # se trouvaient renseignés simultanément.
        if self.options:
            d["typeParameters"] = {
                "values": [o.to_dict() for o in self.options]
            }
        elif self.reference_form_id:
            d["typeParameters"] = {"range": [{"formId": self.reference_form_id}]}
        elif self.units:
            d["typeParameters"] = {"units": self.units}
        elif self.formula:
            d["typeParameters"] = {"formula": self.formula}

        return d

    @classmethod
    def from_dict(cls, data: dict) -> "Field":
        """Crée un Field depuis la réponse JSON de l'API."""
        type_params = data.get("typeParameters", {})
        options = []
        reference_form_id = None
        units = None
        formula = None

        field_type = data.get("type", "FREE_TEXT")

        if field_type in ("SINGLE_SELECTION", "MULTI_SELECTION"):
            options = [
                FieldOption.from_dict(v)
                for v in type_params.get("values", [])
            ]
        elif field_type == "REFERENCE":
            ranges = type_params.get("range", [])
            if ranges:
                reference_form_id = ranges[0].get("formId")
        elif field_type == "QUANTITY":
            units = type_params.get("units")
        elif field_type == "CALCULATED":
            formula = type_params.get("formula")

        return cls(
            id=data["id"],
            label=data.get("label", ""),
            type=field_type,
            code=data.get("code"),
            description=data.get("description"),
            required=data.get("required", False),
            key=data.get("key", False),
            relevance_rule=data.get("relevanceRule"),
            validation_rule=data.get("validationRule"),
            options=options,
            reference_form_id=reference_form_id,
            units=units,
            formula=formula,
            _raw=data,
        )

    def __repr__(self):
        return f"Field(id={self.id!r}, label={self.label!r}, type={self.type!r})"


# ─── Fonctions de création de champs (calquées sur le package R) ───────────────

def text_field(label: str, code: str = None, description: str = None,
               required: bool = False, key: bool = False) -> dict:
    """Crée un champ texte libre. Équivalent de textFieldSchema() en R."""
    from ..utils.cuid import generate_cuid
    d = {"id": generate_cuid(), "label": label, "type": "FREE_TEXT",
         "required": required, "key": key}
    if code: d["code"] = code
    if description: d["description"] = description
    return d


def narrative_field(label: str, code: str = None,
                    required: bool = False) -> dict:
    """Crée un champ texte long (narratif)."""
    from ..utils.cuid import generate_cuid
    return {"id": generate_cuid(), "label": label, "type": "NARRATIVE",
            "required": required, "code": code}


def quantity_field(label: str, code: str = None, units: str = None,
                   required: bool = False) -> dict:
    """Crée un champ numérique. Équivalent de quantityFieldSchema() en R."""
    from ..utils.cuid import generate_cuid
    d = {"id": generate_cuid(), "label": label, "type": "QUANTITY",
         "required": required}
    if code: d["code"] = code
    if units: d["typeParameters"] = {"units": units}
    return d


def date_field(label: str, code: str = None, required: bool = False) -> dict:
    """Crée un champ date."""
    from ..utils.cuid import generate_cuid
    d = {"id": generate_cuid(), "label": label, "type": "DATE",
         "required": required}
    if code: d["code"] = code
    return d


def single_select_field(label: str, options: List[str], code: str = None,
                         required: bool = False,
                         relevance_rule: str = None) -> dict:
    """
    Crée un champ sélection unique.
    Équivalent de singleSelectFieldSchema() en R.
    """
    from ..utils.cuid import generate_cuid
    values = [{"id": generate_cuid(), "label": opt} for opt in options]
    d = {
        "id": generate_cuid(), "label": label,
        "type": "SINGLE_SELECTION", "required": required,
        "typeParameters": {"values": values},
    }
    if code: d["code"] = code
    if relevance_rule: d["relevanceRule"] = relevance_rule
    return d


def multi_select_field(label: str, options: List[str], code: str = None,
                        required: bool = False) -> dict:
    """Crée un champ sélection multiple."""
    from ..utils.cuid import generate_cuid
    values = [{"id": generate_cuid(), "label": opt} for opt in options]
    d = {
        "id": generate_cuid(), "label": label,
        "type": "MULTI_SELECTION", "required": required,
        "typeParameters": {"values": values},
    }
    if code: d["code"] = code
    return d


def reference_field(label: str, form_id: str, code: str = None,
                    required: bool = False) -> dict:
    """Crée un champ référence vers un autre formulaire."""
    from ..utils.cuid import generate_cuid
    d = {
        "id": generate_cuid(), "label": label,
        "type": "REFERENCE", "required": required,
        "typeParameters": {"range": [{"formId": form_id}]},
    }
    if code: d["code"] = code
    return d


def geopoint_field(label: str, code: str = None,
                   required: bool = False) -> dict:
    """Crée un champ géolocalisation (latitude/longitude)."""
    from ..utils.cuid import generate_cuid
    d = {"id": generate_cuid(), "label": label, "type": "GEOPOINT",
         "required": required}
    if code: d["code"] = code
    return d
