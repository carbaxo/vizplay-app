"""
Progreso de reproducción + "visto", en el PC y sincronizado con la nube
(states[perfil].progress, mismo esquema que la web y Android). Port de
`WatchStore.kt`.

    key     = "movie:<tmdb>"  |  "series:<tmdb>:<season>:<episode>"
    titleId = "movie:<tmdb>"  |  "series:<tmdb>"
    "visto" si position/duration > 0.9
"""
from __future__ import annotations

import re
import threading
from datetime import datetime, timezone
from typing import Callable

from . import almacen

_FICHERO = "progreso.json"
lista: list[dict] = []
_lock = threading.RLock()
_oyentes: list[Callable[[], None]] = []


def al_cambiar(fn: Callable[[], None]) -> None:
    _oyentes.append(fn)


def _avisar() -> None:
    for fn in list(_oyentes):
        fn()


def iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def init() -> None:
    with _lock:
        lista[:] = parse(almacen.leer_json(_FICHERO, []))


def _persist() -> None:
    almacen.guardar_json(_FICHERO, lista)


def parse(arr) -> list[dict]:
    """Normaliza lo que venga (nube o disco): mismas claves que Android."""
    out = []
    for o in arr or []:
        if not isinstance(o, dict) or not o.get("key"):
            continue
        key = str(o["key"])
        tid = str(o.get("titleId") or key)
        m = re.search(r"(\d+)", tid)
        try:
            tmdb_id = int(o.get("tmdbId") or (m.group(1) if m else 0))
        except (TypeError, ValueError):
            tmdb_id = 0
        poster = o.get("poster")
        out.append({
            "key": key, "titleId": tid, "tmdbId": tmdb_id,
            "type": "series" if (o.get("type") == "series" or key.startswith("series")) else "movie",
            "season": int(o["season"]) if o.get("season") is not None else None,
            "episode": int(o["episode"]) if o.get("episode") is not None else None,
            "name": str(o.get("name") or ""),
            "poster": poster if poster and poster != "null" else None,
            "position": float(o.get("position") or 0), "duration": float(o.get("duration") or 0),
            "watched": bool(o.get("watched")), "updatedAt": str(o.get("updatedAt") or ""),
        })
    return out


def to_maps() -> list[dict]:
    """Para Firestore: sin claves a None, como hace Android."""
    with _lock:
        return [{k: v for k, v in p.items() if v is not None} for p in lista]


def load_from_maps(maps: list) -> None:
    """Sustituye lo local por lo de la nube (al elegir perfil)."""
    with _lock:
        lista[:] = parse(maps)
        _persist()
    _avisar()


def record(tmdb_id: int, tipo: str, season: int | None, episode: int | None, name: str,
           poster: str | None, position: float, duration: float) -> None:
    if tmdb_id <= 0 or position < 5:
        return
    serie = tipo == "series" and season is not None
    title_id = f"{'series' if serie else 'movie'}:{tmdb_id}"
    key = f"series:{tmdb_id}:{season}:{episode or 1}" if serie else f"movie:{tmdb_id}"
    p = {
        "key": key, "titleId": title_id, "tmdbId": tmdb_id, "type": "series" if serie else "movie",
        "season": season if serie else None, "episode": (episode or 1) if serie else None,
        "name": name, "poster": poster, "position": float(position), "duration": float(duration),
        "watched": duration > 0 and position / duration > 0.9, "updatedAt": iso(),
    }
    with _lock:
        lista[:] = [x for x in lista if x["key"] != key]
        lista.insert(0, p)
        _persist()
    _avisar()
    # Empuja a la nube si hay perfil activo (no-op si no hay sesión)
    from . import sync
    sync.save_progress_cloud(to_maps())


def is_watched_title(tipo: str, tmdb_id: int) -> bool:
    tid = f"{'series' if tipo == 'series' else 'movie'}:{tmdb_id}"
    with _lock:
        return any(p["titleId"] == tid and p["watched"] for p in lista)


def is_watched_episode(tmdb_id: int, season: int, episode: int) -> bool:
    key = f"series:{tmdb_id}:{season}:{episode}"
    with _lock:
        return any(p["key"] == key and p["watched"] for p in lista)


def progress_for(key: str) -> dict | None:
    with _lock:
        return next((p for p in lista if p["key"] == key), None)


def continue_watching(tipo: str | None = None) -> list[dict]:
    """Lo empezado y sin acabar, del tipo pedido (en Descubrir, con el filtro en
    Series no tiene sentido ofrecer películas)."""
    with _lock:
        items = [p for p in lista if (tipo is None or p["type"] == tipo) and not p["watched"]
                 and p["position"] > 20 and (p["duration"] <= 0 or p["position"] / p["duration"] < 0.95)]
    return sorted(items, key=lambda p: p["updatedAt"], reverse=True)


def seeds(tipo: str | None = None) -> list[tuple[int, str]]:
    """Semillas para recomendar. El recorte a 6 va DESPUÉS de filtrar por tipo:
    si no, las seis últimas podían ser todas películas y no quedaría ninguna."""
    with _lock:
        items = sorted(lista, key=lambda p: p["updatedAt"], reverse=True)
    out: list[tuple[int, str]] = []
    for p in items:
        par = (p["tmdbId"], p["type"])
        if (tipo is None or p["type"] == tipo) and p["tmdbId"] > 0 and par not in out:
            out.append(par)
    return out[:6]
