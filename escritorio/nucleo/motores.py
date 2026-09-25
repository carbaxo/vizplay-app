"""
Los motores de búsqueda de fuentes: Torrentio, Peerflix y el addon extra, que
hablan todos el protocolo de addons de Stremio. Port de `Addon.kt`,
`Torrentio.kt`, `Peerflix.kt` y `ExtraAddon.kt`.

    película:  BASE/stream/movie/tt1234567.json
    serie:     BASE/stream/series/tt1234567:1:5.json

Ningún motor lanza hacia fuera: si un addon está caído devuelve None (o una
lista vacía) y la búsqueda sigue con los demás. Nunca se queda peor que antes.
"""
from __future__ import annotations

import re

import requests

from . import lang, prefs
from . import search as S
from .red import sesion

_SEEDERS = re.compile(r"(?:👤|seeders?\s*:?)\s*(\d+)", re.I)
# "💾 4.38 GB", "💾 696,71 MB" y variantes sin emoji
_SIZE = re.compile(r"([\d]+[.,]?[\d]*)\s*(TB|GB|MB|GiB|MiB)\b", re.I)


def size_to_bytes(m: re.Match | None) -> int:
    if not m:
        return 0
    try:
        v = float(m.group(1).replace(",", "."))
    except ValueError:
        return 0
    mult = {"TB": 1024 ** 4, "GB": 1024 ** 3, "GIB": 1024 ** 3, "MB": 1024 ** 2, "MIB": 1024 ** 2}
    return int(v * mult.get(m.group(2).upper(), 0))


def stream_size(stream: dict, title: str) -> int:
    """El dato exacto del addon (behaviorHints.videoSize) y si no, el del texto."""
    bh = stream.get("behaviorHints") or {}
    for v in (bh.get("videoSize"), stream.get("size")):
        try:
            if v and int(v) > 0:
                return int(v)
        except (TypeError, ValueError):
            pass
    return size_to_bytes(_SIZE.search(title))


def clean_base(raw: str) -> str:
    """Acepta la URL del addon tal y como se copie: con /manifest.json, con
    /configure o con barra final. Sin esto, pegar la de la web daba 404."""
    s = raw.strip()
    for suf in ("/", "/manifest.json", "/configure", "/"):
        if s.endswith(suf):
            s = s[: -len(suf)]
    return s


def stream_path(tipo: str, imdb_id: str, season: int | None, episode: int | None) -> str:
    kind = "series" if tipo == "series" else "movie"
    ident = f"{imdb_id}:{season}:{episode or 1}" if (kind == "series" and season is not None) else imdb_id
    return f"/stream/{kind}/{ident}.json"


def parse_streams(body: dict, engine: str) -> list[S.Result]:
    """Respuesta de un addon -> resultados. El detalle se lee de `title` Y de
    `description`: los addons antiguos usan el primero y los modernos el segundo."""
    out = []
    for s in body.get("streams") or []:
        h = str(s.get("infoHash") or "").lower()
        if not h:
            continue
        name = str(s.get("name") or "")
        detail = S.pick_detail(str(s.get("title") or ""), str(s.get("description") or ""))
        bh = s.get("behaviorHints") or {}
        combined = f"{name}\n{detail}\n{bh.get('bingeGroup') or ''}"
        filename = S.pick_filename(str(bh.get("filename") or ""), detail, name)
        # 👤 0 NO se descarta: con Real-Debrid puede estar en caché igual.
        seeders = s.get("seeders")
        if not isinstance(seeders, int) or seeders < 0:
            m = _SEEDERS.search(detail)
            seeders = int(m.group(1)) if m else 0
        out.append(S.Result(
            name=filename, info_hash=h, seeders=seeders,
            size_bytes=stream_size(s, detail),
            magnet=S.build_magnet(h, filename),
            lang=lang.detect_from_title(combined),
            quality=S.quality(combined),
            engine=engine,
            info=S.pick_info(detail, filename),
        ))
    return out


def _pedir(url: str, engine: str, timeout=(8, 12)) -> list[S.Result] | None:
    """Tiempos cortos a propósito: si en 12 s no ha contestado, no va a
    contestar, y los enlaces de los demás motores ya se están mostrando."""
    try:
        r = sesion.get(url, timeout=timeout)
        if not r.ok:
            return None
        return parse_streams(r.json(), engine)
    except (requests.RequestException, ValueError):
        return None


def _packs(bases: list[str], imdb_id: str, season: int | None, engine: str) -> list[S.Result]:
    """PACKS de temporada o de serie completa.

    Las series infantiles en castellano (Peppa Pig, Bluey…) casi nunca se
    publican por capítulos: van en packs cuyos ficheros se llaman "04x12.avi",
    que el addon no sabe asociar a un episodio. Se prueban varias formas del id
    porque el protocolo no garantiza que un addon conteste a las otras.
    """
    out: dict[str, S.Result] = {}
    for ident in [imdb_id] + ([f"{imdb_id}:{season}"] if season is not None else []):
        for base in bases:
            r = _pedir(f"{base}/stream/series/{ident}.json", engine)
            if r:
                for x in r:
                    out.setdefault(x.info_hash, x.copy(pack=True))
                break
    return list(out.values())


# ---------------------------------------------------------------- Torrentio
TORRENTIO = "https://torrentio.strem.fun"
# Configuración igual que en Stremio. El endpoint "pelado" solo consulta los
# indexadores por DEFECTO y faltaban justo las fuentes españolas (MejorTorrent,
# Wolfmax4k, Cinecalidad). Si falla, se reintenta sin configurar.
_TORRENTIO_CONFIG = (
    "providers=yts,eztv,rarbg,1337x,thepiratebay,kickasstorrents,torrentgalaxy,"
    "magnetdl,horriblesubs,nyaasi,tokyotosho,anidex,rutor,rutracker,comando,bludv,"
    "torrent9,ilcorsaronero,mejortorrent,wolfmax4k,cinecalidad|sort=qualitysize"
)


def torrentio_streams(tipo, imdb_id, season, episode) -> list[S.Result] | None:
    path = stream_path(tipo, imdb_id, season, episode)
    r = _pedir(f"{TORRENTIO}/{_TORRENTIO_CONFIG}{path}", S.ENGINE_TORRENTIO, timeout=(10, 20))
    if r:
        return r
    return _pedir(f"{TORRENTIO}{path}", S.ENGINE_TORRENTIO, timeout=(10, 20))


def torrentio_packs(imdb_id, season) -> list[S.Result]:
    return _packs([f"{TORRENTIO}/{_TORRENTIO_CONFIG}", TORRENTIO], imdb_id, season, S.ENGINE_TORRENTIO)


# ----------------------------------------------------------------- Peerflix
PEERFLIX_DEFAULT = "https://peerflix.mov"


def _peerflix_base() -> str:
    return clean_base(prefs.peerflix_url() or PEERFLIX_DEFAULT)


def peerflix_streams(tipo, imdb_id, season, episode) -> list[S.Result] | None:
    return _pedir(_peerflix_base() + stream_path(tipo, imdb_id, season, episode), S.ENGINE_PEERFLIX)


def peerflix_packs(imdb_id, season) -> list[S.Result]:
    return _packs([_peerflix_base()], imdb_id, season, S.ENGINE_PEERFLIX)


# -------------------------------------------------------------- Addon extra
# Un addon de Stremio cualquiera, a elección del usuario (MediaFusion, Comet,
# Jackettio…). Vacío = no existe y no se pregunta a nadie. No hace falta
# configurarlo con Real-Debrid: la app manda el magnet a RD por su cuenta.
def extra_configured() -> bool:
    return bool(prefs.extra_addon_url().strip())


def extra_streams(tipo, imdb_id, season, episode) -> list[S.Result] | None:
    if not extra_configured():
        return []
    return _pedir(clean_base(prefs.extra_addon_url()) + stream_path(tipo, imdb_id, season, episode),
                  S.ENGINE_EXTRA)


def extra_packs(imdb_id, season) -> list[S.Result]:
    if not extra_configured():
        return []
    return _packs([clean_base(prefs.extra_addon_url())], imdb_id, season, S.ENGINE_EXTRA)


def extra_test(url: str | None = None) -> str:
    """Prueba de conexión para Ajustes: sin ella no se distingue «esta película
    no tiene enlaces» de «la URL que he pegado no vale»."""
    base = clean_base(url if url is not None else prefs.extra_addon_url())
    if not base:
        return "Pon primero la URL del addon."
    # El caballero oscuro: si un addon de películas funciona, esta la tiene
    try:
        r = sesion.get(base + stream_path("movie", "tt0468569", None, None), timeout=(8, 12))
    except requests.RequestException as e:
        return f"No se pudo conectar: {e.__class__.__name__}"
    if not r.ok:
        return f"El addon respondió {r.status_code}. Revisa la URL."
    try:
        n = len(parse_streams(r.json(), S.ENGINE_EXTRA))
    except ValueError:
        return "Responde, pero no es un addon de Stremio (no devuelve JSON)."
    if n:
        return f"✅ Funciona: {n} enlaces de prueba."
    return "Responde, pero sin enlaces. Puede que necesite una URL con tu configuración dentro."
