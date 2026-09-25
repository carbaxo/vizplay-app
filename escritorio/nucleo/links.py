"""
Arregla los enlaces pegados, que casi nunca llegan limpios. Port de `Links.kt`.

 - Fragmento de texto de Chrome: «copiar enlace al texto resaltado» añade
   `#:~:text=…`, que solo entiende el navegador.
 - Falta el esquema: `dontorrent.management/serie/…` sin el `https://`.
"""
from __future__ import annotations

import re


def tidy(raw: str) -> str:
    s = raw.strip().strip("\"'<>")
    s = s.split("#:~:", 1)[0]
    if s.lower().startswith(("magnet:", "http")):
        return s
    if re.match(r"^[a-z0-9.-]+\.[a-z]{2,}(/|$)", s, re.I):
        return "https://" + s
    return s


def looks_truncated(s: str) -> bool:
    """¿Enlace al que le falta el principio (dominio incluido)? No se puede
    reconstruir, pero sí dar un aviso que se entienda."""
    v = s.strip()
    if v.lower().startswith(("magnet:", "http")):
        return False
    return bool(re.match(r"^/?\d+/", v)) or (v.startswith("/") and v.count("/") >= 2) or \
        (v.count("/") >= 2 and " " not in v and "." not in v)
