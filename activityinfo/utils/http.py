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


def raise_for_error(response: requests.Response) -> None:
    """
    Lève l'exception ActivityInfo appropriée si la réponse HTTP
    indique une erreur. Ne fait rien si la réponse est un succès.

    200/201 : succès avec corps (ex : GET, POST création)
    204     : succès sans corps (ex : DELETE) — n'est PAS une erreur.
    """
    status = response.status_code

    if status in (200, 201, 204):
        return

    # Extraire le message d'erreur si disponible.
    # Si le serveur répond en HTML (page de connexion, page d'erreur
    # générique...) plutôt qu'en JSON, c'est généralement le signe d'un
    # problème d'authentification ou d'URL, pas d'une vraie erreur
    # applicative : on évite de recracher toute la page HTML brute dans
    # le message d'exception et on donne un indice exploitable à la place.
    content_type = response.headers.get("Content-Type", "")
    try:
        error_data = response.json()
        message = error_data.get("message", response.text)
    except ValueError:
        if "html" in content_type.lower():
            message = (
                "Le serveur a répondu avec une page HTML au lieu de JSON "
                "(souvent le signe d'un token invalide/expiré ou d'une "
                "URL de serveur incorrecte, plutôt que d'une erreur "
                "applicative). Vérifiez votre token API et server_url."
            )
        else:
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


def handle_response(response: requests.Response) -> dict:
    """
    Analyse la réponse HTTP, lève l'exception appropriée en cas d'erreur,
    et retourne le JSON parsé si succès (dict vide si pas de contenu,
    par ex. sur une réponse 204).
    """
    raise_for_error(response)
    try:
        return response.json() if response.content else {}
    except ValueError:
        return {}


def safe_request(session: requests.Session, method: str,
                 url: str, **kwargs) -> dict:
    """
    Exécute une requête HTTP sécurisée avec gestion complète des erreurs.
    Retourne le corps JSON parsé (dict).
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


def safe_request_binary(session: requests.Session, method: str,
                        url: str, **kwargs) -> bytes:
    """
    Variante de safe_request pour les réponses binaires (ex : pièces
    jointes / blobs) : mêmes garanties de gestion d'erreurs et de
    timeout que safe_request, mais retourne des bytes bruts au lieu
    de tenter un parsing JSON.
    """
    timeout = kwargs.pop("timeout", getattr(session, "_default_timeout", 30))
    logger.debug(f"{method.upper()} {url}")

    try:
        response = session.request(method, url, timeout=timeout, **kwargs)
        raise_for_error(response)
        return response.content

    except requests.exceptions.ConnectionError as e:
        raise ConnectionError(f"Impossible de joindre ActivityInfo : {e}")
    except requests.exceptions.Timeout as e:
        raise TimeoutError(f"Délai d'attente dépassé : {e}")
    except (AuthenticationError, NotFoundError, PermissionError,
            RateLimitError, ServerError, ActivityInfoError):
        raise  # Re-raise nos exceptions personnalisées
    except requests.exceptions.RequestException as e:
        raise ActivityInfoError(f"Erreur réseau inattendue : {e}")
