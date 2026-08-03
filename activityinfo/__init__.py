"""
activityinfo
~~~~~~~~~~~~
Client Python complet pour l'API ActivityInfo.
"""

from .client import ActivityInfoClient
from .models.field import (
    text_field, narrative_field, quantity_field, date_field,
    single_select_field, multi_select_field, reference_field, geopoint_field,
)

__all__ = [
    "ActivityInfoClient",
    "text_field", "narrative_field", "quantity_field", "date_field",
    "single_select_field", "multi_select_field", "reference_field", "geopoint_field",
]

__version__ = "0.1.0"
