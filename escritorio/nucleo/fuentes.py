"""
La búsqueda de fuentes de la ficha y el «siguiente episodio». Es la parte de
`MainActivity.kt` (DetailScreen.runSearch) y de `PlayerActivity.kt`
(trySources / pickSameKind) que no es interfaz.
"""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Callable

from . import motores, prefs, rd_engine, realdebrid, tmdb
from . import search as S

_pool = ThreadPoolExecutor(max_workers=12, thread_name_prefix="motor")


def buscar(title: str, tipo: str, imdb_id: str | None, season: int | None, episode: int | None,
           parcial: Callable[[list[S.Result], bool], None]) -> str | None:
    """Pregunta a TODOS los motores a la vez y va llamando a `parcial(lista, fin)`
    conforme contesta cada uno, en vez de esperar al más lento: un addon atascado
    dejaba la ficha en blanco veinte segundos aunque los otros ya hubieran
    contestado. Devuelve un mensaje si no se pudo buscar.

    En series se pregunta además por los PACKS de temporada: en castellano lo
    normal es que una serie se publique entera y no capítulo a capítulo.
    """
    usable = imdb_id is not None and (tipo == "movie" or episode is not None)
    if not usable:
        if not realdebrid.configured():
            return "No se pudo identificar el título (sin IMDb id)" if imdb_id is None \
                else "Elige un episodio para ver sus enlaces"
        # Sin IMDb id solo se puede mirar en tu cuenta, por nombre
        parcial(S.sort_by_engine_and_lang(rd_engine.streams(title), prefs.language_order()), True)
        return None

    tareas: list[Callable[[], list[S.Result] | None]] = [
        lambda: motores.extra_streams(tipo, imdb_id, season, episode),
        lambda: motores.peerflix_streams(tipo, imdb_id, season, episode),
        lambda: motores.torrentio_streams(tipo, imdb_id, season, episode),
        # Tu propia cuenta de RD, por NOMBRE: lo añadido a mano sale aquí
        lambda: rd_engine.streams(title),
    ]
    if tipo == "series":
        tareas += [
            lambda: motores.extra_packs(imdb_id, season),
            lambda: motores.peerflix_packs(imdb_id, season),
            lambda: motores.torrentio_packs(imdb_id, season),
        ]
    acc: list[S.Result] = []
    futuros = [_pool.submit(t) for t in tareas]
    restantes = len(futuros)
    for fut in as_completed(futuros):
        restantes -= 1
        try:
            r = fut.result()
        except Exception:  # noqa: BLE001 - un motor roto no tumba la búsqueda
            r = None
        if r:
            acc.extend(S.relevantes(r, season, episode))
        parcial(S.sort_by_engine_and_lang(S.merge_results(acc), prefs.language_order()), restantes == 0)
    return None


def pick_same_kind(items: list[S.Result], engine: str, quality: str, lang_code: str | None) -> S.Result | None:
    """El enlace más parecido al que se estaba viendo: mismo motor, luego misma
    calidad e idioma; si no hay nada igual, se relaja hasta el mejor por idioma
    y semillas. Así el siguiente episodio no pasa de castellano a inglés."""
    if not items:
        return None
    by_lang = S.sort_by_lang(items, prefs.language_order())
    first = engine.split("+")[0] if engine else ""
    same = [r for r in by_lang if not first or r.from_engine(first)] or by_lang
    q = quality if quality and quality != "Unknown" else None
    for cond in (lambda r: q and r.quality == q and lang_code and r.lang == lang_code,
                 lambda r: q and r.quality == q,
                 lambda r: lang_code and r.lang == lang_code):
        hit = next((r for r in same if cond(r)), None)
        if hit:
            return hit
    return same[0]


def next_episode(tmdb_id: int, season: int, episode: int, engine: str, quality: str,
                 lang_code: str | None) -> dict:
    """Busca el siguiente capítulo con el mismo motor y lo resuelve en RD.
    Si era el último de la temporada, prueba el 1 de la siguiente."""
    if not realdebrid.configured():
        return {"error": "Conecta Real-Debrid en Ajustes para el siguiente episodio"}
    imdb = tmdb.imdb_id("series", tmdb_id)
    if not imdb:
        return {"error": "No se pudo identificar la serie"}
    no_torrentio = S.ENGINE_TORRENTIO not in engine
    for s, e in ((season, episode + 1), (season + 1, 1)):
        # Mismo motor que el episodio que se veía: si venía de Peerflix o del
        # extra es que estaba en castellano, y seguir con Torrentio lo dejaría en
        # inglés a mitad de serie.
        if S.ENGINE_EXTRA in engine and no_torrentio:
            lst = motores.extra_streams("series", imdb, s, e)
        elif S.ENGINE_PEERFLIX in engine and no_torrentio:
            lst = motores.peerflix_streams("series", imdb, s, e)
        else:
            lst = motores.torrentio_streams("series", imdb, s, e)
        lst = [r for r in S.relevantes(lst or [], s, e) if not r.pack]
        best = pick_same_kind(lst, engine, quality, lang_code)
        if not best:
            continue
        for _ in range(20):
            r = realdebrid.stream_magnet(best.magnet)
            if r.get("url"):
                return {"url": r["url"], "season": s, "episode": e, "result": best.to_dict()}
            if "progress" not in r:
                return {"error": r.get("error") or "Error de Real-Debrid"}
        return {"error": "Real-Debrid sigue preparando el siguiente episodio; prueba en un momento."}
    return {"error": "No hay fuentes del siguiente episodio"}


def episode_alerts(favs: list[dict]) -> list[dict]:
    """Avisos de episodios nuevos (port de `EpisodeAlerts.kt`): se compara el
    último emitido de cada serie favorita con el de la última comprobación.
    Solo avisa si ya se conocía uno anterior distinto."""
    if not tmdb.has_key():
        return []
    vistos: dict = dict(prefs.get("lastEp") or {})
    avisos = []
    for f in [f for f in favs if f.get("type") == "series"][:12]:
        last = tmdb.last_episode(f["tmdbId"])
        if not last or last[0] <= 0 or last[1] <= 0:
            continue
        s, e, name = last
        now, prev = f"{s}:{e}", vistos.get(str(f["tmdbId"]))
        vistos[str(f["tmdbId"])] = now
        if prev is not None and prev != now:
            avisos.append({"tmdbId": f["tmdbId"], "title": f["title"], "poster": f.get("poster"),
                           "text": f"Nuevo episodio: T{s}E{e}" + (f" · {name}" if name else "")})
    prefs.set("lastEp", vistos)
    return avisos
