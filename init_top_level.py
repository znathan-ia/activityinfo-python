"""
activityinfo
~~~~~~~~~~~~
Package Python complet pour l'API ActivityInfo, inspiré du package R
bedatadriven/activityinfo-R.
"""

from .client import ActivityInfoClient
from .exceptions import (
    ActivityInfoError,
    AuthenticationError,
    NotFoundError,
    PermissionError,
    RateLimitError,
    ServerError,
    ValidationError,
    ConnectionError,
    TimeoutError,
    JobError,
)
from .models.database import Database, DatabaseResource, DatabaseUser
from .models.form import FormSchema, FormRecord
from .models.field import (
    Field,
    FieldOption,
    text_field,
    barcode_field,
    narrative_field,
    quantity_field,
    date_field,
    week_field,
    month_field,
    single_select_field,
    multi_select_field,
    reference_field,
    user_field,
    calculated_field,
    subform_field,
    serial_field,
    attachment_field,
    geopoint_field,
)

__version__ = "0.1.0"

__all__ = [
    "ActivityInfoClient",
    "ActivityInfoError",
    "AuthenticationError",
    "NotFoundError",
    "PermissionError",
    "RateLimitError",
    "ServerError",
    "ValidationError",
    "ConnectionError",
    "TimeoutError",
    "JobError",
    "Database",
    "DatabaseResource",
    "DatabaseUser",
    "FormSchema",
    "FormRecord",
    "Field",
    "FieldOption",
    "text_field",
    "barcode_field",
    "narrative_field",
    "quantity_field",
    "date_field",
    "week_field",
    "month_field",
    "single_select_field",
    "multi_select_field",
    "reference_field",
    "user_field",
    "calculated_field",
    "subform_field",
    "serial_field",
    "attachment_field",
    "geopoint_field",
]
