"""
Idiomas: detección del idioma de cada fuente por su nombre y orden de
preferencia. Port de `Lang.kt`.
"""
from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass(frozen=True)
class Info:
    code: str        # clave interna
    label: str       # etiqueta para la UI
    flag: str        # emoji bandera
    tmdb: str        # idioma TMDB (para catálogos/fichas)
    keywords: tuple  # palabras clave YA normalizadas (ver normalize)


# Palabras clave **ya normalizadas**: en minúsculas y rodeadas de espacios,
# porque normalize() convierte puntos, guiones y corchetes en espacios. Así
# `[CAST]`, `.Cast.` y `-CAST-` casan todos con " cast ", y en cambio «podcast» o
# «Castle» no, que era el riesgo de buscar «cast» a pelo.
ALL: list[Info] = [
    Info("es-ES", "Español (España)", "🇪🇸", "es-ES",
         (" castellano ", " espanol ", " español ", " spanish ", " cast ", " esp ",
          " spa ", " es es ", " espana ", " españa ", " castellano dual ")),
    Info("es-LA", "Español (Latino)", "🇲🇽", "es-MX",
         (" latino ", " latin ", " lat ", " espanol latino ", " mx ", " latam ")),
    Info("en", "Inglés", "🇬🇧", "en-US",
         (" english ", " eng ", " vose ", " v o s ", " vo ")),
    Info("multi", "Multi-idioma", "🌍", "es-ES",
         (" multi ", " dual ")),
]

DEFAULT_ORDER = ["es-ES", "en"]


def by_code(code: str | None) -> Info | None:
    return next((i for i in ALL if i.code == code), None)


# Banderas emoji (Torrentio las incluye en el título de cada fuente) -> código
_FLAGS = {
    "🇪🇸": "es-ES",
    "🇲🇽": "es-LA", "🇦🇷": "es-LA", "🇨🇴": "es-LA", "🇨🇱": "es-LA",
    "🇵🇪": "es-LA", "🇻🇪": "es-LA", "🇺🇾": "es-LA",
    "🇺🇸": "en", "🇬🇧": "en",
}


def detect_from_title(title: str) -> str | None:
    """Detecta idioma priorizando las BANDERAS del título (Torrentio).

    Si entre las banderas está la de España **gana el castellano**, aunque haya
    más: un enlace con 🇪🇸🇬🇧 se puede ver en castellano, y marcarlo como «multi»
    lo hundía en la lista de quien tiene el español como idioma preferido. Solo
    es «multi» cuando hay varias y ninguna es la española.
    """
    found = list(dict.fromkeys(v for k, v in _FLAGS.items() if k in title))
    if "es-ES" in found:
        return "es-ES"
    if len(found) >= 2:
        return "multi"
    if len(found) == 1:
        return found[0]
    return detect(title)


def from_tmdb(tmdb: str | None) -> str | None:
    """Mapea un idioma en formato TMDB (es-ES, en-US, es-MX) a nuestro código."""
    return {
        "es-ES": "es-ES",
        "es-MX": "es-LA", "es-419": "es-LA",
        "en-US": "en", "en-GB": "en", "en": "en",
    }.get(tmdb or "")


_SEP = re.compile(r"[._\-\[\]()/+,;:!¡?¿|]")
_ESP = re.compile(r"\s+")


def normalize(name: str) -> str:
    """Nombre listo para buscar palabras: minúsculas y separadores a espacios."""
    return " " + _ESP.sub(" ", _SEP.sub(" ", name.lower())).strip() + " "


def detect(name: str) -> str | None:
    """Idioma de un nombre de torrent, o None si no hay pistas claras.

    **El castellano se comprueba ANTES que multi/dual**, y es a propósito: un
    «Oliver y Benji Dual Castellano Japonés» se marcaba como «multi» y con el
    idioma puesto en castellano se hundía en la lista. Un dual con castellano
    dentro **se puede ver en castellano**, que es lo único que importa aquí.
    """
    n = normalize(name)
    for code in ("es-ES", "es-LA", "multi", "en"):
        if any(k in n for k in by_code(code).keywords):
            return code
    return None


def flag(code: str | None) -> str:
    info = by_code(code)
    return info.flag if info else "🏳️"


def label(code: str | None) -> str:
    info = by_code(code)
    return info.label if info else "Idioma desconocido"


def rank(code: str | None, order: list[str]) -> int:
    """Cuanto antes en la lista, menor. Desconocidos y no listados, al final."""
    if code is None:
        return len(order) + 2
    return order.index(code) if code in order else len(order) + 1
