"""
Catálogos y fichas desde TMDB, directamente desde el PC, sin backend.
Port de `Tmdb.kt`.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from urllib.parse import urlencode

from . import prefs
from .red import ErrorRed, get_json

IMG = "https://image.tmdb.org/t/p/w342"
BACKDROP = "https://image.tmdb.org/t/p/w1280"
STILL = "https://image.tmdb.org/t/p/w300"
API = "https://api.themoviedb.org/3"
REGION = "ES"


@dataclass(frozen=True)
class Platform:
    key: str
    name: str
    providers: str


PLATFORMS = [
    Platform("netflix", "Netflix", "8"),
    Platform("prime", "Prime Video", "9|119"),
    Platform("hbomax", "HBO Max", "384|1899|118"),
    Platform("disney", "Disney+", "337"),
]

GENRES = {
    "movie": [(28, "Acción"), (35, "Comedia"), (18, "Drama"), (27, "Terror"),
              (878, "Ciencia ficción"), (16, "Animación"), (53, "Thriller"),
              (10749, "Romance"), (12, "Aventura"), (80, "Crimen"), (99, "Documental"), (14, "Fantasía")],
    "series": [(10759, "Acción y aventura"), (35, "Comedia"), (18, "Drama"), (16, "Animación"),
               (80, "Crimen"), (9648, "Misterio"), (10765, "Ciencia ficción y fantasía"),
               (99, "Documental"), (10751, "Familia")],
}


def _kids_genres(tipo: str) -> str:
    # Familia (10751) / Animación (16) / Kids (10762, solo TV), como la web
    return "10762|16|10751" if tipo == "series" else "10751|16"


def has_key() -> bool:
    return bool(prefs.tmdb_key())


def _tt(tipo: str) -> str:
    return "tv" if tipo == "series" else "movie"


def _get(path: str, con_idioma: bool = True, **params) -> dict:
    q = {"api_key": prefs.tmdb_key()}
    if con_idioma:
        q["language"] = prefs.primary_tmdb_lang()
    q.update({k: v for k, v in params.items() if v is not None})
    try:
        return get_json(f"{API}{path}?{urlencode(q)}", timeout=(10, 15))
    except ErrorRed as e:
        if "401" in str(e):
            raise ErrorRed("TMDB rechaza la clave (401). Revísala en Ajustes → Catálogos.") from e
        raise ErrorRed(f"TMDB {e}") from e


@dataclass(frozen=True)
class Title:
    tmdbId: int
    title: str
    originalTitle: str
    year: str
    poster: str | None
    rating: float
    type: str  # "movie" | "series"

    def to_dict(self) -> dict:
        return asdict(self)


def _map_title(o: dict, tipo: str) -> Title | None:
    movie = tipo == "movie"
    title = (o.get("title") or o.get("original_title")) if movie else (o.get("name") or o.get("original_name"))
    if not title:
        return None
    date = (o.get("release_date") if movie else o.get("first_air_date")) or ""
    poster = o.get("poster_path") or ""
    return Title(
        tmdbId=int(o.get("id") or 0),
        title=title,
        originalTitle=(o.get("original_title") if movie else o.get("original_name")) or title,
        year=date[:4] if len(date) >= 4 else "",
        poster=IMG + poster if poster else None,
        rating=int(float(o.get("vote_average") or 0) * 10) / 10.0,
        type=tipo,
    )


def _titles(d: dict, tipo: str) -> list[Title]:
    return [t for t in (_map_title(o, tipo) for o in d.get("results") or []) if t]


def catalogs(tipo: str, kids: bool = False) -> list[dict]:
    """Una fila por plataforma. Una que falle no tumba el resto."""
    rows = []
    for p in PLATFORMS:
        try:
            d = _get(f"/discover/{_tt(tipo)}", with_watch_providers=p.providers, watch_region=REGION,
                     with_watch_monetization_types="flatrate", sort_by="popularity.desc", page=1,
                     with_genres=_kids_genres(tipo) if kids else None)
        except ErrorRed:
            continue
        items = _titles(d, tipo)
        if items:
            rows.append({"name": p.name, "provider": p.providers, "items": [t.to_dict() for t in items]})
    if not rows:
        raise ErrorRed("No se pudieron cargar los catálogos.")
    return rows


def discover(tipo: str, provider: str | None, genre_id: int | None, page: int, kids: bool = False) -> list[Title]:
    """Explorar (paginado) por plataforma o género."""
    params = dict(sort_by="popularity.desc", page=page)
    params["vote_count.gte"] = 30
    if provider:
        params.update(with_watch_providers=provider, watch_region=REGION, with_watch_monetization_types="flatrate")
    # En modo infantil se restringe a géneros familiares (salvo género concreto)
    if genre_id is not None:
        params["with_genres"] = genre_id
    elif kids:
        params["with_genres"] = _kids_genres(tipo)
    return _titles(_get(f"/discover/{_tt(tipo)}", **params), tipo)


def search_text(query: str, tipo: str) -> list[Title]:
    return _titles(_get(f"/search/{_tt(tipo)}", include_adult="false", query=query, page=1), tipo)


def detail(tipo: str, tmdb_id: int) -> dict:
    d = _get(f"/{_tt(tipo)}/{tmdb_id}")
    movie = tipo == "movie"
    date = (d.get("release_date") if movie else d.get("first_air_date")) or ""
    seasons = []
    if not movie:
        # Fuera especiales (temporada 0) y temporadas vacías
        for s in d.get("seasons") or []:
            num, eps = s.get("season_number", -1), s.get("episode_count", 0)
            if num and num > 0 and eps and eps > 0:
                seasons.append({"season": num, "name": s.get("name") or f"Temporada {num}", "episodes": eps})
    poster, back = d.get("poster_path") or "", d.get("backdrop_path") or ""
    title = d.get("title") if movie else d.get("name")
    return {
        "tmdbId": int(d.get("id") or tmdb_id),
        "type": tipo,
        "title": title or "",
        "originalTitle": (d.get("original_title") if movie else d.get("original_name")) or title or "",
        "year": date[:4] if len(date) >= 4 else "",
        "overview": d.get("overview") or "",
        "backdrop": BACKDROP + back if back else None,
        "poster": IMG + poster if poster else None,
        "rating": int(float(d.get("vote_average") or 0) * 10) / 10.0,
        "genres": [g.get("name", "") for g in (d.get("genres") or [])][:4],
        "runtime": d.get("runtime") or 0,
        "seasons": seasons,
    }


def recommendations(seeds: list[tuple[int, str]]) -> list[Title]:
    """A partir de semillas [(tmdbId, tipo)] (máx. 6)."""
    out: dict[int, Title] = {}
    seed_ids = {s[0] for s in seeds}
    for tmdb_id, tipo in seeds[:6]:
        try:
            d = _get(f"/{_tt(tipo)}/{tmdb_id}/recommendations", page=1)
        except ErrorRed:
            continue
        for t in _titles(d, tipo):
            if t.tmdbId not in seed_ids and t.tmdbId not in out:
                out[t.tmdbId] = t
    return list(out.values())[:30]


def trailer(tipo: str, tmdb_id: int) -> str | None:
    """Clave de YouTube del tráiler: en el idioma preferido y luego en inglés,
    priorizando Trailer oficial > Trailer > Teaser."""
    def pick(d: dict) -> str | None:
        yt = [o for o in d.get("results") or [] if o.get("site") == "YouTube" and o.get("key")]
        for cond in (lambda v: v.get("type") == "Trailer" and v.get("official"),
                     lambda v: v.get("type") == "Trailer",
                     lambda v: v.get("type") == "Teaser",
                     lambda v: True):
            for v in yt:
                if cond(v):
                    return v["key"]
        return None
    try:
        return pick(_get(f"/{_tt(tipo)}/{tmdb_id}/videos")) or \
            pick(_get(f"/{_tt(tipo)}/{tmdb_id}/videos", con_idioma=False))
    except ErrorRed:
        return None


def last_episode(tmdb_id: int) -> tuple[int, int, str] | None:
    """Último episodio emitido de una serie (para los avisos)."""
    try:
        le = _get(f"/tv/{tmdb_id}").get("last_episode_to_air")
    except ErrorRed:
        return None
    if not le:
        return None
    return int(le.get("season_number") or 0), int(le.get("episode_number") or 0), le.get("name") or ""


def imdb_id(tipo: str, tmdb_id: int) -> str | None:
    """IMDb id (ttXXXXXXX), necesario para los addons."""
    try:
        i = _get(f"/{_tt(tipo)}/{tmdb_id}/external_ids", con_idioma=False).get("imdb_id") or ""
    except ErrorRed:
        return None
    return i if i.startswith("tt") else None


def episodes(tmdb_id: int, season: int) -> list[dict]:
    d = _get(f"/tv/{tmdb_id}/season/{season}")
    out = []
    for e in d.get("episodes") or []:
        still = e.get("still_path") or ""
        n = int(e.get("episode_number") or 0)
        out.append({
            "episode": n,
            "name": e.get("name") or f"Episodio {n}",
            "overview": e.get("overview") or "",
            "still": STILL + still if still else None,
            "runtime": e.get("runtime") or 0,
            "airDate": e.get("air_date") or "",
        })
    return out
