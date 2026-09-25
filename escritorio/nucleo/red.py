"""Cliente HTTP común (el OkHttpClient de la app Android)."""
from __future__ import annotations

import requests

AGENTE = "VizPlay"

sesion = requests.Session()
sesion.headers.update({"User-Agent": AGENTE})


class ErrorRed(RuntimeError):
    """Fallo de red o respuesta no válida, con un mensaje que se puede enseñar."""


def get_json(url: str, timeout: float = 15, **kw):
    try:
        r = sesion.get(url, timeout=timeout, **kw)
    except requests.RequestException as e:
        raise ErrorRed(f"Error de red: {e.__class__.__name__}") from e
    if not r.ok:
        raise ErrorRed(f"respondió {r.status_code}")
    try:
        return r.json()
    except ValueError as e:
        raise ErrorRed("respuesta que no es JSON") from e
