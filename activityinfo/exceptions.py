"""
activityinfo.exceptions
~~~~~~~~~~~~~~~~~~~~~~~
Exceptions personnalisées pour le package ActivityInfo Python.
"""


class ActivityInfoError(Exception):
    """Erreur de base du package ActivityInfo."""
    pass


class AuthenticationError(ActivityInfoError):
    """Token invalide, expiré ou absent."""
    pass


class NotFoundError(ActivityInfoError):
    """Ressource introuvable (404)."""
    pass


class PermissionError(ActivityInfoError):
    """Accès refusé à la ressource (403)."""
    pass


class RateLimitError(ActivityInfoError):
    """Quota API dépassé (429)."""
    pass


class ServerError(ActivityInfoError):
    """Erreur serveur ActivityInfo (5xx)."""
    pass


class ValidationError(ActivityInfoError):
    """Données invalides ou schéma incorrect."""
    pass


class ConnectionError(ActivityInfoError):
    """Impossible de joindre le serveur ActivityInfo."""
    pass


class TimeoutError(ActivityInfoError):
    """Délai d'attente dépassé."""
    pass


class JobError(ActivityInfoError):
    """Erreur lors de l'exécution d'un job asynchrone."""
    def __init__(self, message, job_id=None):
        super().__init__(message)
        self.job_id = job_id
