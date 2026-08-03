"""
activityinfo.models.field
~~~~~~~~~~~~~~~~~~~~~~~~~
Modèles pour les champs de formulaires ActivityInfo.
Inspiré de fieldSchema() du package R bedatadriven.
"""

from dataclasses import dataclass, field
from typing import Optional, List, Any, Dict, Literal

# Types de champs réellement acceptés par l'API ActivityInfo,
# confirmés depuis R/formField.R du package R officiel.
FIELD_TYPES = Literal[
    "FREE_TEXT",    # texte libre (et code-barres, via typeParameters.barcode)
    "NARRATIVE",    # texte long / multi-lignes
    "quantity",
    "date",
    "epiweek",      # champ "semaine" (convention EPI week)
    "month",
    "enumerated",   # sélection unique ou multiple, voir cardinality
    "reference",    # référence vers un autre formulaire (ou un utilisateur)
    "attachment",
    "geopoint",
    "calculated",
    "serial",
    "subform",
]


@dataclass
class FieldOption:
    """Option pour un champ 'enumerated' (sélection unique ou multiple)."""
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

    Équivalent des fonctions *FieldSchema() dans R/formField.R.
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

    # Pour "enumerated" (sélection) et "reference"
    cardinality: Optional[str] = None  # "single" ou "multiple"

    # Pour "enumerated"
    options: List[FieldOption] = field(default_factory=list)

    # Pour "reference"
    reference_form_id: Optional[str] = None

    # Pour "quantity"
    units: Optional[str] = None
    aggregation: Optional[str] = None  # défaut API : "SUM"

    # Pour "calculated"
    formula: Optional[str] = None

    # Pour "FREE_TEXT" (un champ code-barres est un FREE_TEXT avec barcode=True)
    barcode: bool = False

    # Pour "attachment"
    capture_methods: List[str] = field(default_factory=list)

    # Pour "subform"
    subform_id: Optional[str] = None

    # Pour "geopoint"
    manual_entry_allowed: Optional[bool] = None
    required_accuracy: Optional[float] = None

    # Pour "serial"
    digits: Optional[int] = None
    prefix_formula: Optional[str] = None

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

        # La forme de typeParameters dépend strictement du type du champ.
        if self.type == "FREE_TEXT":
            d["typeParameters"] = {"barcode": self.barcode}
        elif self.type == "quantity":
            d["typeParameters"] = {
                "units": self.units or "",
                "aggregation": self.aggregation or "SUM",
            }
        elif self.type == "enumerated":
            d["typeParameters"] = {
                "cardinality": self.cardinality or "single",
                "presentation": "automatic",
                "values": [o.to_dict() for o in self.options],
            }
        elif self.type == "reference":
            d["typeParameters"] = {
                "cardinality": self.cardinality or "single",
                "range": [{"formId": self.reference_form_id}],
            }
        elif self.type == "attachment":
            d["typeParameters"] = {
                "cardinality": "multiple",
                "captureMethods": self.capture_methods or ["CAMERA", "FILE", "SIGNATURE"],
            }
        elif self.type == "calculated":
            d["typeParameters"] = {"formula": self.formula}
        elif self.type == "subform":
            d["typeParameters"] = {"formId": self.subform_id}
        elif self.type == "geopoint":
            params: Dict[str, Any] = {
                "manualEntryAllowed": (
                    self.manual_entry_allowed
                    if self.manual_entry_allowed is not None else True
                ),
            }
            if self.required_accuracy is not None:
                params["requiredAccuracy"] = self.required_accuracy
            d["typeParameters"] = params
        elif self.type == "serial":
            params = {"digits": self.digits if self.digits is not None else 5}
            if self.prefix_formula:
                params["prefixFormula"] = self.prefix_formula
            d["typeParameters"] = params
        # NARRATIVE, date, epiweek, month n'ont pas de typeParameters.

        return d

    @classmethod
    def from_dict(cls, data: dict) -> "Field":
        """Crée un Field depuis la réponse JSON de l'API."""
        type_params = data.get("typeParameters", {}) or {}
        field_type = data.get("type", "FREE_TEXT")

        options = []
        reference_form_id = None
        units = None
        aggregation = None
        formula = None
        cardinality = None
        barcode = False
        capture_methods = []
        subform_id = None
        manual_entry_allowed = None
        required_accuracy = None
        digits = None
        prefix_formula = None

        if field_type == "FREE_TEXT":
            barcode = bool(type_params.get("barcode", False))
        elif field_type == "quantity":
            units = type_params.get("units")
            aggregation = type_params.get("aggregation")
        elif field_type == "enumerated":
            cardinality = type_params.get("cardinality")
            options = [
                FieldOption.from_dict(v)
                for v in type_params.get("values", [])
            ]
        elif field_type == "reference":
            cardinality = type_params.get("cardinality")
            ranges = type_params.get("range", [])
            if ranges:
                reference_form_id = ranges[0].get("formId")
        elif field_type == "attachment":
            capture_methods = type_params.get("captureMethods", [])
        elif field_type == "calculated":
            formula = type_params.get("formula")
        elif field_type == "subform":
            subform_id = type_params.get("formId")
        elif field_type == "geopoint":
            manual_entry_allowed = type_params.get("manualEntryAllowed")
            required_accuracy = type_params.get("requiredAccuracy")
        elif field_type == "serial":
            digits = type_params.get("digits")
            prefix_formula = type_params.get("prefixFormula")

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
            cardinality=cardinality,
            options=options,
            reference_form_id=reference_form_id,
            units=units,
            aggregation=aggregation,
            formula=formula,
            barcode=barcode,
            capture_methods=capture_methods,
            subform_id=subform_id,
            manual_entry_allowed=manual_entry_allowed,
            required_accuracy=required_accuracy,
            digits=digits,
            prefix_formula=prefix_formula,
            _raw=data,
        )

    def __repr__(self):
        return f"Field(id={self.id!r}, label={self.label!r}, type={self.type!r})"


# ─── Fonctions de création de champs (calquées sur R/formField.R) ─────────────

def text_field(label: str, code: str = None, description: str = None,
               required: bool = False, key: bool = False) -> dict:
    """Crée un champ texte libre. Équivalent de textFieldSchema() en R."""
    from ..utils.cuid import generate_cuid
    d = {"id": generate_cuid(), "label": label, "type": "FREE_TEXT",
         "required": required, "key": key,
         "typeParameters": {"barcode": False}}
    if code: d["code"] = code
    if description: d["description"] = description
    return d


def barcode_field(label: str, code: str = None, description: str = None,
                   required: bool = False, key: bool = False) -> dict:
    """Crée un champ code-barres. Équivalent de barcodeFieldSchema() en R
    (techniquement un FREE_TEXT avec typeParameters.barcode = True)."""
    from ..utils.cuid import generate_cuid
    d = {"id": generate_cuid(), "label": label, "type": "FREE_TEXT",
         "required": required, "key": key,
         "typeParameters": {"barcode": True}}
    if code: d["code"] = code
    if description: d["description"] = description
    return d


def narrative_field(label: str, code: str = None,
                    required: bool = False) -> dict:
    """Crée un champ texte long (narratif). Équivalent de multilineFieldSchema()."""
    from ..utils.cuid import generate_cuid
    d = {"id": generate_cuid(), "label": label, "type": "NARRATIVE",
         "required": required}
    if code: d["code"] = code
    return d


def quantity_field(label: str, code: str = None, units: str = "",
                   aggregation: str = "SUM", required: bool = False) -> dict:
    """Crée un champ numérique. Équivalent de quantityFieldSchema() en R."""
    from ..utils.cuid import generate_cuid
    d = {"id": generate_cuid(), "label": label, "type": "quantity",
         "required": required,
         "typeParameters": {"units": units, "aggregation": aggregation}}
    if code: d["code"] = code
    return d


def date_field(label: str, code: str = None, required: bool = False) -> dict:
    """Crée un champ date. Équivalent de dateFieldSchema() en R."""
    from ..utils.cuid import generate_cuid
    d = {"id": generate_cuid(), "label": label, "type": "date",
         "required": required}
    if code: d["code"] = code
    return d


def week_field(label: str, code: str = None, required: bool = False) -> dict:
    """Crée un champ semaine (convention EPI week). Équivalent de weekFieldSchema()."""
    from ..utils.cuid import generate_cuid
    d = {"id": generate_cuid(), "label": label, "type": "epiweek",
         "required": required}
    if code: d["code"] = code
    return d


def month_field(label: str, code: str = None, required: bool = False) -> dict:
    """Crée un champ mois. Équivalent de monthFieldSchema() en R."""
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
    Équivalent de singleSelectFieldSchema() en R : type="enumerated",
    typeParameters.cardinality="single".
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
    if relevance_rule: d["relevanceRule"] = relevance_rule
    return d


def multi_select_field(label: str, options: List[str], code: str = None,
                        required: bool = False) -> dict:
    """Crée un champ sélection multiple. Équivalent de multipleSelectFieldSchema()
    en R : type="enumerated", typeParameters.cardinality="multiple"."""
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
    """Crée un champ référence vers un autre formulaire.
    Équivalent de referenceFieldSchema() en R : type="reference"."""
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


def user_field(label: str, database_id: str, code: str = None,
              required: bool = False) -> dict:
    """Crée un champ de sélection d'utilisateur. Équivalent de userFieldSchema()
    en R : c'est en réalité un champ "reference" pointant vers le
    pseudo-formulaire "{database_id}@users"."""
    from ..utils.cuid import generate_cuid
    d = {
        "id": generate_cuid(), "label": label,
        "type": "reference", "required": required,
        "typeParameters": {
            "cardinality": "single",
            "range": [{"formId": f"{database_id}@users"}],
        },
    }
    if code: d["code"] = code
    return d


def calculated_field(label: str, formula: str, code: str = None) -> dict:
    """Crée un champ calculé. Équivalent de calculatedFieldSchema() en R."""
    from ..utils.cuid import generate_cuid
    d = {
        "id": generate_cuid(), "label": label, "type": "calculated",
        "typeParameters": {"formula": formula},
    }
    if code: d["code"] = code
    return d


def subform_field(label: str, subform_id: str, code: str = None) -> dict:
    """Crée un champ sous-formulaire. Équivalent de subformFieldSchema() en R."""
    from ..utils.cuid import generate_cuid
    d = {
        "id": generate_cuid(), "label": label, "type": "subform",
        "typeParameters": {"formId": subform_id},
    }
    if code: d["code"] = code
    return d


def serial_field(label: str, digits: int = 5, prefix_formula: str = None,
                 code: str = None) -> dict:
    """Crée un champ numéro de série. Équivalent de serialNumberFieldSchema()
    en R. Un seul champ serial est possible par formulaire ; il est
    automatiquement required=True et key=True côté API."""
    from ..utils.cuid import generate_cuid
    params: Dict[str, Any] = {"digits": digits}
    if prefix_formula:
        params["prefixFormula"] = prefix_formula
    d = {
        "id": generate_cuid(), "label": label, "type": "serial",
        "required": True, "key": True,
        "typeParameters": params,
    }
    if code: d["code"] = code
    return d


def attachment_field(label: str, code: str = None,
                     required: bool = False) -> dict:
    """Crée un champ pièce jointe. Équivalent de attachmentFieldSchema() en R."""
    from ..utils.cuid import generate_cuid
    d = {
        "id": generate_cuid(), "label": label, "type": "attachment",
        "required": required,
        "typeParameters": {
            "cardinality": "multiple",
            "captureMethods": ["CAMERA", "FILE", "SIGNATURE"],
        },
    }
    if code: d["code"] = code
    return d


def geopoint_field(label: str, code: str = None,
                   required: bool = False,
                   manual_entry_allowed: bool = True,
                   required_accuracy: float = None) -> dict:
    """Crée un champ géolocalisation (latitude/longitude).
    Équivalent de geopointFieldSchema() en R."""
    from ..utils.cuid import generate_cuid
    params: Dict[str, Any] = {"manualEntryAllowed": manual_entry_allowed}
    if required_accuracy is not None:
        params["requiredAccuracy"] = required_accuracy
    d = {"id": generate_cuid(), "label": label, "type": "geopoint",
         "required": required, "typeParameters": params}
    if code: d["code"] = code
    return d
