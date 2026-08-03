"""
activityinfo.models.form
~~~~~~~~~~~~~~~~~~~~~~~~
Modèle pour les formulaires ActivityInfo.
Inspiré de formSchema() et getFormSchema() du package R.
"""

from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any

from .field import Field


@dataclass
class FormSchema:
    """
    Représente le schéma complet d'un formulaire ActivityInfo.
    Équivalent de getFormSchema() dans le package R.
    """
    id: str
    label: str
    database_id: str
    fields: List[Field] = field(default_factory=list)
    schema_version: Optional[int] = None
    description: Optional[str] = None
    sub_form_kind: Optional[str] = None   # REPEATING, etc.
    parent_form_id: Optional[str] = None

    _raw: Dict[str, Any] = field(default_factory=dict, repr=False)

    @classmethod
    def from_dict(cls, data: dict) -> "FormSchema":
        """Construit un FormSchema depuis la réponse JSON de l'API."""
        fields_list = [
            Field.from_dict(e)
            for e in data.get("elements", [])
        ]
        return cls(
            id=data["id"],
            label=data.get("label", ""),
            database_id=data.get("databaseId", ""),
            fields=fields_list,
            schema_version=data.get("schemaVersion"),
            description=data.get("description"),
            sub_form_kind=data.get("subFormKind"),
            parent_form_id=data.get("parentFormId"),
            _raw=data,
        )

    def to_dict(self) -> dict:
        """Sérialise le schéma pour l'API (création / mise à jour)."""
        d: Dict[str, Any] = {
            "id": self.id,
            "label": self.label,
            "databaseId": self.database_id,
            "elements": [f.to_dict() for f in self.fields],
        }
        if self.schema_version is not None:
            d["schemaVersion"] = self.schema_version
        if self.description:
            d["description"] = self.description
        if self.sub_form_kind:
            d["subFormKind"] = self.sub_form_kind
        if self.parent_form_id:
            d["parentFormId"] = self.parent_form_id
        return d

    def get_field(self, code_or_label: str) -> Optional[Field]:
        """Récupère un champ par son code ou son label."""
        for f in self.fields:
            if f.code == code_or_label or f.label == code_or_label:
                return f
        return None

    def field_codes(self) -> List[str]:
        """Retourne la liste des codes de tous les champs."""
        return [f.code or f.id for f in self.fields]

    def __repr__(self):
        return (f"FormSchema(id={self.id!r}, label={self.label!r}, "
                f"fields={len(self.fields)})")


@dataclass
class FormRecord:
    """
    Représente un enregistrement d'un formulaire ActivityInfo.
    """
    record_id: str
    form_id: str
    values: Dict[str, Any] = field(default_factory=dict)
    last_edit_time: Optional[float] = None

    @classmethod
    def from_dict(cls, data: dict, form_id: str = "") -> "FormRecord":
        return cls(
            record_id=data.get("recordId", data.get("id", "")),
            form_id=form_id,
            values=data.get("fields", data.get("values", {})),
            last_edit_time=data.get("lastEditTime"),
        )

    def to_dict(self) -> dict:
        return {
            "recordId": self.record_id,
            "formId": self.form_id,
            "fields": self.values,
        }

    def __repr__(self):
        return f"FormRecord(record_id={self.record_id!r}, form_id={self.form_id!r})"
