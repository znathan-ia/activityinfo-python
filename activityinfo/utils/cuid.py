"""
activityinfo.utils.cuid
~~~~~~~~~~~~~~~~~~~~~~~
Générateur de CUID (Collision-resistant Unique IDentifier).
ActivityInfo utilise les CUIDs comme identifiants uniques pour
les bases, formulaires, enregistrements, etc.

Voir : https://www.activityinfo.org/support/docs/api/concepts/cuids.html
"""

import time
import random
import string
import threading

_lock = threading.Lock()
_counter = 0
_BLOCK_SIZE = 4
_BASE = 36
_DISCRETE_VALUES = _BASE ** _BLOCK_SIZE


def _to_base36(number: int, block_size: int = 0) -> str:
    """Convertit un entier en base 36."""
    chars = string.digits + string.ascii_lowercase
    result = ""
    while number > 0:
        result = chars[number % _BASE] + result
        number //= _BASE
    result = result or "0"
    if block_size:
        result = result.zfill(block_size)
    return result


def generate_cuid() -> str:
    """
    Génère un CUID unique compatible avec ActivityInfo.

    Format : c + timestamp + counter + fingerprint + random
    Exemple : cjld2cjxh0000qzrmn831i7rn
    """
    global _counter

    # Timestamp en millisecondes (base 36)
    timestamp = _to_base36(int(time.time() * 1000))

    # Compteur thread-safe
    with _lock:
        _counter = (_counter + 1) % _DISCRETE_VALUES
        count_str = _to_base36(_counter, _BLOCK_SIZE)

    # Fingerprint (simplifié)
    fingerprint = _to_base36(
        random.randint(0, _DISCRETE_VALUES - 1), _BLOCK_SIZE
    )

    # Bloc aléatoire
    rand1 = _to_base36(
        random.randint(0, _DISCRETE_VALUES - 1), _BLOCK_SIZE
    )
    rand2 = _to_base36(
        random.randint(0, _DISCRETE_VALUES - 1), _BLOCK_SIZE
    )

    return f"c{timestamp}{count_str}{fingerprint}{rand1}{rand2}"


def is_valid_cuid(value: str) -> bool:
    """Vérifie si une chaîne est un CUID valide."""
    if not isinstance(value, str):
        return False
    if not value.startswith("c"):
        return False
    if len(value) < 25:
        return False
    valid_chars = set(string.digits + string.ascii_lowercase)
    return all(c in valid_chars for c in value)
