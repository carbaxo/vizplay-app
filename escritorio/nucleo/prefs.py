"""
Preferencias locales del PC. Port de `Prefs.kt`, con lo que cambia en
escritorio: la carpeta de descargas es una ruta normal (no hace falta el SAF de
Android) y el reproductor externo es VLC o mpv instalados en Windows.

También guarda aquí la **clave de TMDB**. En Android va compilada dentro del
APK desde un secreto de GitHub; aquí el repositorio es público y la app no se
compila, así que se pega una vez en Ajustes (o se pone en la variable de
entorno TMDB_KEY).
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Callable

from . import almacen, lang

_FICHERO = "prefs.json"

PLAYER_APP = "app"     # el reproductor propio
PLAYER_VLC = "vlc"     # siempre VLC, sin preguntar
PLAYER_ASK = "ask"     # preguntar cada vez

_datos: dict = {}
_oyentes: list[Callable[[], None]] = []


def al_cambiar(fn: Callable[[], None]) -> None:
    _oyentes.append(fn)


def _avisar() -> None:
    for fn in list(_oyentes):
        fn()


def init() -> None:
    global _datos
    _datos = almacen.leer_json(_FICHERO, {})
    orden = [c for c in _datos.get("langOrder", []) if lang.by_code(c)]
    _datos["langOrder"] = orden or list(lang.DEFAULT_ORDER)


def _guardar() -> None:
    almacen.guardar_json(_FICHERO, _datos)
    _avisar()


def get(clave: str, defecto=None):
    return _datos.get(clave, defecto)


def set(clave: str, valor) -> None:  # noqa: A001 - mismo nombre que en Kotlin
    _datos[clave] = valor
    _guardar()


# ---------------------------------------------------------------- idiomas
def language_order() -> list[str]:
    return list(_datos.get("langOrder") or lang.DEFAULT_ORDER)


def set_language_order(order: list[str], subir: bool = True) -> None:
    _datos["langOrder"] = [c for c in order if lang.by_code(c)] or list(lang.DEFAULT_ORDER)
    _guardar()
    if subir:
        # Sube el idioma principal a la nube (settings del perfil), como la web
        from . import sync
        sync.save_settings_language(primary_tmdb_lang())


def primary_tmdb_lang() -> str:
    """Idioma principal en formato TMDB (para catálogos y fichas)."""
    orden = language_order()
    info = lang.by_code(orden[0] if orden else "es-ES")
    return info.tmdb if info else "es-ES"


# --------------------------------------------------------------- buscadores
def engine() -> str:
    """Motor elegido en la ficha; se recuerda entre títulos, como Stremio."""
    return _datos.get("engine", "all")


def peerflix_url() -> str:
    return _datos.get("peerflixUrl", "")


def extra_addon_url() -> str:
    return _datos.get("extraAddonUrl", "")


# ------------------------------------------------------------- reproducción
def player_mode() -> str:
    return _datos.get("playerMode", PLAYER_APP)


# ---------------------------------------------------------------- descargas
def download_dir() -> Path:
    """Carpeta de descargas. Por defecto Descargas\\VizPlay, a la vista y fuera
    de la carpeta de datos de la app: sobrevive a desinstalar."""
    propia = _datos.get("downloadDir", "")
    if propia:
        return Path(propia)
    return Path.home() / "Downloads" / "VizPlay"


# --------------------------------------------------------------------- TMDB
def tmdb_key() -> str:
    return (os.environ.get("TMDB_KEY") or _datos.get("tmdbKey", "") or _clave_empaquetada()).strip()


def _clave_empaquetada() -> str:
    """Clave que pueda dejar la CI junto al programa (tmdb_key.txt, ignorado por git)."""
    try:
        return (Path(__file__).resolve().parent.parent / "tmdb_key.txt").read_text(encoding="utf-8").strip()
    except OSError:
        return ""
