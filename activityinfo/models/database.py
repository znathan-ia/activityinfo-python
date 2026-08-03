"""
activityinfo.models.database
~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Modèles pour les bases de données ActivityInfo.
Inspiré de getDatabases() / getDatabaseResources() du package R.
"""

from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any


@dataclass
class Database:
    """
    Représente une base de données ActivityInfo.
    Équivalent de getDatabases() dans le package R.
    """
    id: str
    label: str
    description: Optional[str] = None
    owner_name: Optional[str] = None
    owner_email: Optional[str] = None
    billing_account_id: Optional[str] = None

    _raw: Dict[str, Any] = field(default_factory=dict, repr=False)

    @classmethod
    def from_dict(cls, data: dict) -> "Database":
        return cls(
            id=data.get("databaseId", data.get("id", "")),
            label=data.get("label", ""),
            description=data.get("description"),
            owner_name=data.get("ownerName"),
            owner_email=data.get("ownerEmail"),
            billing_account_id=data.get("billingAccountId"),
            _raw=data,
        )

    def __repr__(self):
        return f"Database(id={self.id!r}, label={self.label!r})"


@dataclass
class DatabaseResource:
    """
    Représente une ressource dans une base de données
    (formulaire, sous-formulaire, dossier, rapport...).
    Équivalent de getDatabaseResources() dans le package R.
    """
    id: str
    label: str
    type: str           # FORM, SUB_FORM, FOLDER, REPORT
    parent_id: Optional[str] = None
    visibility: Optional[str] = None   # PRIVATE, REFERENCE, PUBLIC

    _raw: Dict[str, Any] = field(default_factory=dict, repr=False)

    @classmethod
    def from_dict(cls, data: dict) -> "DatabaseResource":
        return cls(
            id=data.get("id", ""),
            label=data.get("label", ""),
            type=data.get("type", ""),
            parent_id=data.get("parentId"),
            visibility=data.get("visibility"),
            _raw=data,
        )

    @property
    def is_form(self) -> bool:
        return self.type == "FORM"

    @property
    def is_folder(self) -> bool:
        return self.type == "FOLDER"

    @property
    def is_sub_form(self) -> bool:
        return self.type == "SUB_FORM"

    def __repr__(self):
        return (f"DatabaseResource(id={self.id!r}, "
                f"label={self.label!r}, type={self.type!r})")


@dataclass
class DatabaseUser:
    """Représente un utilisateur d'une base de données."""
    user_id: Optional[int] = None
    name: Optional[str] = None
    email: Optional[str] = None
    role_id: Optional[str] = None
    role_label: Optional[str] = None
    locale: Optional[str] = "fr"

    _raw: Dict[str, Any] = field(default_factory=dict, repr=False)

    @classmethod
    def from_dict(cls, data: dict) -> "DatabaseUser":
        return cls(
            user_id=data.get("userId"),
            name=data.get("name"),
            email=data.get("email"),
            role_id=data.get("roleId"),
            role_label=data.get("roleLabel"),
            locale=data.get("locale", "fr"),
            _raw=data,
        )

    def __repr__(self):
        return f"DatabaseUser(email={self.email!r}, role={self.role_id!r})"
