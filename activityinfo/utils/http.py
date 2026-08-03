"""
activityinfo.utils.http
~~~~~~~~~~~~~~~~~~~~~~~
Session HTTP robuste avec retry, timeout et gestion d'erreurs.
"""

import logging
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from ..exceptions import (
    ActivityInfoError, AuthenticationError, NotFoundError,
    PermissionError, RateLimitError, ServerError,
    ConnectionError, TimeoutError
)

logger = logging.getLogger("activityinfo")

BASE_URL = "https://www.activityinfo.org"


def build_session(token: str, timeout: int = 30) -> requests.Session:
    """
    Construit une session requests robuste avec :
    - Authentification Bearer
    - Retry automatique (3 tentatives sur erreurs réseau/5xx)
    - Backoff exponentiel
    - Timeout global
    """
    session = requests.Session()
    session.headers.update({
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "Accept": "application/json",
    })

    retry_strategy = Retry(
        total=3,
        backoff_factor=1.5,
        status_forcelist=[500, 502, 503, 504],
        allowed_methods=["GET", "POST", "PUT", "DELETE", "PATCH"],
        raise_on_status=False,
    )
    adapter = HTTPAdapter(max_retries=retry_strategy)
    session.mount("https://", adapter)
    session.mount("http://", adapter)

    # Stocker le timeout dans la session pour usage global
    session._default_timeout = timeout

    return session


def handle_response(response: requests.Response) -> dict:
    """
    Analyse la réponse HTTP et lève l'exception appropriée.
    Retourne le JSON parsé si succès.
    """
    status = response.status_code

    if status == 200 or status == 201:
        try:
            return response.json() if response.content else {}
        except ValueError:
            return {}

    # Extraire le message d'erreur si disponible
    try:
        error_data = response.json()
        message = error_data.get("message", response.text)
    except ValueError:
        message = response.text or f"Erreur HTTP {status}"

    if status == 401:
        raise AuthenticationError(f"Token invalide ou expiré : {message}")
    elif status == 403:
        raise PermissionError(f"Accès refusé : {message}")
    elif status == 404:
        raise NotFoundError(f"Ressource introuvable : {message}")
    elif status == 429:
        raise RateLimitError(f"Quota API dépassé. Réessayez plus tard : {message}")
    elif 500 <= status < 600:
        raise ServerError(f"Erreur serveur ActivityInfo ({status}) : {message}")
    else:
        raise ActivityInfoError(f"Erreur inattendue ({status}) : {message}")


def safe_request(session: requests.Session, method: str,
                 url: str, **kwargs) -> dict:
    """
    Exécute une requête HTTP sécurisée avec gestion complète des erreurs.
    """
    timeout = kwargs.pop("timeout", getattr(session, "_default_timeout", 30))
    logger.debug(f"{method.upper()} {url}")

    try:
        response = session.request(method, url, timeout=timeout, **kwargs)
        return handle_response(response)

    except requests.exceptions.ConnectionError as e:
        raise ConnectionError(f"Impossible de joindre ActivityInfo : {e}")
    except requests.exceptions.Timeout as e:
        raise TimeoutError(f"Délai d'attente dépassé : {e}")
    except (AuthenticationError, NotFoundError, PermissionError,
            RateLimitError, ServerError, ActivityInfoError):
        raise  # Re-raise nos exceptions personnalisées
    except requests.exceptions.RequestException as e:
        raise ActivityInfoError(f"Erreur réseau inattendue : {e}")
