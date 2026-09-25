"""
Busca en **tu propia cuenta de Real-Debrid** y lo ofrece como un motor más en la
ficha. Port de `RdEngine.kt`.

Es lo que cierra el círculo: cuando un título no aparece en ningún addon (las
series infantiles en castellano), se añade el torrent a mano una vez y a partir
de ahí **sale solo en la ficha**. Va el primero porque usa la API oficial y lo
que sale ya está en tu cuenta: se ve al instante.
"""
from __future__ import annotations

import re
import time

from . import lang, realdebrid
from . import search as S

_TTL = 60.0
_cache: list[dict] = []
_cache_at = 0.0
_NO_PALABRA = re.compile(r"[^\w]+", re.UNICODE)
_STOP = {"the", "los", "las", "una", "unos", "unas", "del", "por", "con", "para"}
_PACK = re.compile(r"temporada|completa|complete|season|\d+x\d+\s*al\s*\d+x\d+|pack|s\d{2}(?!e\d)", re.I)


def _tokens(s: str) -> list[str]:
    return [t for t in _NO_PALABRA.sub(" ", s.lower()).replace("_", " ").split() if len(t) >= 3 and t not in _STOP]


def _matches(title: str, torrent_name: str) -> bool:
    """TODAS las palabras del título tienen que estar en el nombre del torrent:
    así «Peppa Pig» encuentra «Peppa.Pig.1.Temporada.1x01.al.1x13.HDTV»."""
    t = _tokens(title)
    if not t:
        return False
    n = _NO_PALABRA.sub(" ", torrent_name.lower()).replace("_", " ")
    return all(x in n for x in t)


def _to_result(t: dict) -> S.Result:
    name = t["name"]
    return S.Result(
        name=name, info_hash=t["hash"], seeders=t["seeders"], size_bytes=t["bytes"],
        magnet=S.build_magnet(t["hash"], name),
        # Lo que se añade a mano es casi siempre castellano; si el nombre dice
        # otra cosa, se respeta.
        lang=lang.detect_from_title(name) or "es-ES",
        quality=S.quality(name), engine=S.ENGINE_RD,
        info="✅ en tu Real-Debrid" if t["ready"] else f"⏳ en tu Real-Debrid ({t['statusEs']})",
        # Varios archivos = pack, aunque el nombre no lo diga
        pack=bool(_PACK.search(name)) or t["links"] > 1,
    )


def streams(title: str) -> list[S.Result]:
    """Nunca falla hacia fuera: si RD no contesta, lista vacía."""
    global _cache, _cache_at
    if not realdebrid.configured():
        return []
    if not (_cache and time.monotonic() - _cache_at < _TTL):
        try:
            _cache, _cache_at = realdebrid.torrents(), time.monotonic()
        except realdebrid.ErrorRD:
            return []
    return [_to_result(t) for t in _cache if _matches(title, t["name"])]


def invalidate() -> None:
    """Se llama al añadir algo, para que salga ya en la ficha."""
    global _cache_at
    _cache_at = 0.0
