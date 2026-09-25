"""
Modelo de un enlace y utilidades compartidas por los motores de búsqueda.
Port de `Search.kt`.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field, replace
from enum import Enum
from functools import cmp_to_key
from urllib.parse import quote_plus

from . import lang

ENGINE_TORRENTIO = "torrentio"
ENGINE_PEERFLIX = "peerflix"   # addon de Stremio (webs españolas)
ENGINE_EXTRA = "extra"         # addon de Stremio a elección del usuario
ENGINE_RD = "rd"               # tu propia cuenta de Real-Debrid
ENGINE_ALL = "all"


@dataclass(frozen=True)
class Result:
    name: str
    info_hash: str
    seeders: int
    size_bytes: int
    magnet: str
    lang: str | None = None          # código de idioma detectado (lang), o None
    quality: str = "Unknown"         # 4K/1080p/720p/480p/SD/Unknown
    # Motor(es) que lo devolvieron: extra, peerflix, torrentio, unidos con "+".
    engine: str = ""
    # Texto extra del addon (fuente, códec, grupo…). Es lo único que distingue
    # dos enlaces cuando el addon no manda el nombre del fichero.
    info: str = ""
    # Es un PACK (temporada o serie completa): hay que elegir capítulo dentro.
    pack: bool = False

    def from_engine(self, e: str) -> bool:
        """¿Lo devolvió este motor? (un enlace puede venir de varios)."""
        return e == ENGINE_ALL or e in self.engine

    @property
    def engine_label(self) -> str:
        return "+".join(engine_name(e) for e in self.engine.split("+") if e)

    def copy(self, **cambios) -> "Result":
        return replace(self, **cambios)

    def to_dict(self) -> dict:
        return {
            "name": self.name, "infoHash": self.info_hash, "seeders": self.seeders,
            "sizeBytes": self.size_bytes, "size": human_size(self.size_bytes),
            "magnet": self.magnet, "lang": self.lang, "flag": lang.flag(self.lang),
            "langLabel": lang.label(self.lang), "quality": self.quality,
            "engine": self.engine, "engineLabel": self.engine_label,
            "info": self.info, "pack": self.pack,
        }


def engine_name(e: str) -> str:
    return {
        ENGINE_TORRENTIO: "Torrentio",
        ENGINE_PEERFLIX: "Peerflix",
        ENGINE_EXTRA: "Extra",
        ENGINE_RD: "En tu cuenta",   # no es una fuente: ya lo tienes en RD
        ENGINE_ALL: "Todos",
    }.get(e, e[:1].upper() + e[1:])


def pick_detail(title: str, description: str) -> str:
    """Texto descriptivo de un stream de addon.

    Los addons viejos lo ponen en `title` y los nuevos en `description` (el SDK
    de Stremio lo renombró). Leyendo solo `title`, los enlaces de un addon
    moderno salen SIN nombre, SIN tamaño y con 0 seeders: parecen muertos.
    """
    t, d = title.strip(), description.strip()
    if not t:
        return d
    if not d or d == t:
        return t
    return f"{t}\n{d}"


def pick_filename(hinted: str, detail: str, label: str) -> str:
    """Nombre a mostrar: el del addon, la 1.ª línea útil del texto o la etiqueta."""
    if hinted.strip():
        return hinted.strip()
    for line in (l.strip() for l in detail.split("\n")):
        if line and not line.startswith("👤") and not line.startswith("💾"):
            return line
    return label.replace("\n", " ").strip()


def _norm(s: str) -> str:
    return re.sub(r"[^a-z0-9]", "", s.lower())


def pick_info(detail: str, filename: str) -> str:
    """Lo que queda del texto una vez fuera lo que ya se muestra en su sitio
    (nombre, semillas, tamaño). Lo que sobrevive es lo que añade algo: la
    fuente (🌐), el grupo, el códec, las pistas de audio…"""
    fn = _norm(filename)
    out = []
    for line in (l.strip() for l in detail.split("\n")):
        if not line:
            continue
        n = _norm(line)
        if n and fn and (n == fn or n[:40] in fn or fn[:40] in n):
            continue
        line = re.sub(r"👤\s*[\d.,]+", " ", line)
        line = re.sub(r"💾\s*[\d.,]+\s*(TB|GB|MB|GiB|MiB)", " ", line, flags=re.I)
        line = re.sub(r"\s{2,}", " ", line).strip().strip("·-| ")
        if line:
            out.append(line)
    return "  ·  ".join(out)[:200]


_TROZOS = re.compile(r"\d+|\D+")


def natural_compare(a: str, b: str) -> int:
    """Compara "04x2" y "04x10" por el VALOR de los números: sin esto, la lista
    de capítulos de un pack sale 1, 10, 11, 2, 20…"""
    ra, rb = _TROZOS.findall(a.lower()), _TROZOS.findall(b.lower())
    for x, y in zip(ra, rb):
        if x.isdigit() and y.isdigit():
            c = (int(x) > int(y)) - (int(x) < int(y))
        else:
            c = (x > y) - (x < y)
        if c:
            return c
    return len(ra) - len(rb)


natural_key = cmp_to_key(natural_compare)


def best_name(a: str, b: str) -> str:
    """De dos nombres del mismo torrent, el que informa más (un fichero real)."""
    def score(s: str) -> int:
        n = min(len(s), 80)
        if re.search(r"\.(mkv|mp4|avi|webm|m4v)\b", s, re.I):
            n += 100
        if re.search(r"(19|20)\d{2}", s):
            n += 20
        return n
    return b if score(b) > score(a) else a


def merge_engines(a: str, b: str) -> str:
    return "+".join(sorted({e for e in a.split("+") + b.split("+") if e}))


# Primero lo que ya está en TU Real-Debrid (se ve al instante); luego el addon
# extra (si alguien lo configuró es porque busca algo que los otros no dan); y
# Peerflix antes que Torrentio porque indexa las webs españolas.
_ENGINE_ORDER = [ENGINE_RD, ENGINE_EXTRA, ENGINE_PEERFLIX, ENGINE_TORRENTIO]


def engine_priority(engine: str) -> int:
    prios = [(_ENGINE_ORDER.index(e) if e in _ENGINE_ORDER else len(_ENGINE_ORDER))
             for e in engine.split("+") if e]
    return min(prios) if prios else len(_ENGINE_ORDER)


def sort_by_engine_and_lang(items: list[Result], order: list[str]) -> list[Result]:
    return sorted(items, key=lambda r: (engine_priority(r.engine), lang.rank(r.lang, order), -r.seeders))


def sort_by_lang(items: list[Result], order: list[str]) -> list[Result]:
    return sorted(items, key=lambda r: (lang.rank(r.lang, order), -r.seeders))


QUALITIES = ["4K", "1080p", "720p", "480p", "SD"]
QUALITY_OTHER = "Unknown"


def quality(name: str) -> str:
    """Calidad por el nombre. Reconoce también las formas de las webs españolas
    ("[MicroHD][1080 px]", "1920x1080"). Lo que no se identifica queda como
    Unknown y sale en el chip "Otras": nunca se esconde."""
    n = name.lower()
    if re.search(r"\b(4k|2160\s?p?x?|uhd)\b", n) or "3840x2160" in n:
        return "4K"
    if re.search(r"\b1080\s?(p|px)?\b", n) or "1920x1080" in n or re.search(r"\b(fhd|fullhd|full hd)\b", n):
        return "1080p"
    if re.search(r"\b720\s?(p|px)?\b", n) or "1280x720" in n or re.search(r"\bhdtv\b", n):
        return "720p"
    if re.search(r"\b480\s?(p|px)?\b", n) or "854x480" in n:
        return "480p"
    if re.search(r"\b(sd|dvdrip|dvdscr|cam|telesync|ts|360p|240p)\b", n):
        return "SD"
    return "Unknown"


class Fit(Enum):
    OK = "ok"      # es ESE episodio (o no se puede saber: no se esconde)
    PACK = "pack"  # es un pack que lo contiene: hay que elegir capítulo dentro
    NO = "no"      # dice claramente que es OTRO episodio u otra temporada


def _flat(s: str) -> str:
    return " " + re.sub(r"\s+", " ", re.sub(r"[._\-\[\]()/+,;:|]", " ", s.lower())).strip() + " "


_EP_SxE = re.compile(r"\bs(\d{1,2})\s*e(\d{1,3})\b")
_EP_NxN = re.compile(r"\b(\d{1,2})x(\d{1,3})\b")
# Forma española: Cap.1101 = 11x01; Cap.901 = 9x01. El segundo número es
# opcional porque los packs se escriben "Cap.104_106".
_EP_CAP = re.compile(r"\bcap\s*(\d{3,4})(?:\s+(\d{3,4}))?\b")
_EP_RANGO = re.compile(r"\b(\d{1,2})x(\d{1,3})\s*(?:al|a|-|to)\s*(\d{1,2})x(\d{1,3})\b")
# "Temporada 3" y "3 Temporada": en español se escriben las dos.
_TEMPORADA = re.compile(r"\b(?:temporada|temp|season)\s*(\d{1,2})\b|\b(\d{1,2})\s*(?:temporada|temp)\b")
_SOLO_S = re.compile(r"\bs(\d{1,2})\b")
_SERIE_COMPLETA = re.compile(
    r"serie completa|complete series|todas las temporadas|coleccion completa|complete collection|"
    r"seasons?\s*\d+\s*(?:to|a|-)\s*\d+"
)


def episode_fit(name: str, season: int, episode: int) -> Fit:
    """¿Vale este enlace para (temporada, episodio)?

    Regla de oro: **solo se descarta lo que dice claramente que es otra cosa**.
    Si del nombre no se saca temporada ni episodio, pasa. Casos reales en
    `tests/test_search.py`.
    """
    n = _flat(name)

    # 1) Rango de capítulos: "1x01 al 1x13"
    m = _EP_RANGO.search(n)
    if m:
        s1, e1, s2, e2 = (int(g) for g in m.groups())
        dentro = ((season == s1 and episode >= e1 and (season < s2 or episode <= e2))
                  or (s1 < season < s2)
                  or (season == s2 and season != s1 and episode <= e2))
        return Fit.PACK if dentro else Fit.NO

    # 2) Episodios concretos. Puede haber varios (packs que los listan).
    vistos: list[tuple[int, int]] = []
    vistos += [(int(a), int(b)) for a, b in _EP_SxE.findall(n)]
    vistos += [(int(a), int(b)) for a, b in _EP_NxN.findall(n)]
    for m in _EP_CAP.finditer(n):
        for d in m.groups():
            if not d:
                continue
            s = int(d[:2]) if len(d) == 4 else int(d[:1])   # 4 cifras SSEE, 3 cifras SEE
            vistos.append((s, int(d[-2:])))
    if vistos:
        if (season, episode) in vistos:
            return Fit.OK
        # Dos o más de la MISMA temporada son un rango implícito ("Cap.104_106")
        mismos = sorted(e for s, e in vistos if s == season)
        if len(mismos) >= 2 and mismos[0] <= episode <= mismos[-1]:
            return Fit.PACK
        return Fit.NO

    # 3) Serie completa: sirve para cualquier episodio
    if _SERIE_COMPLETA.search(n):
        return Fit.PACK

    # 4) Solo temporada declarada, sin episodio: pack de esa temporada
    temps = {int(g) for m in _TEMPORADA.finditer(n) for g in m.groups() if g}
    temps |= {int(g) for g in _SOLO_S.findall(n)}
    if temps:
        return Fit.PACK if season in temps else Fit.NO

    # 5) Del nombre no se saca nada: no se esconde
    return Fit.OK


_TRACKERS = [
    "udp://tracker.opentrackr.org:1337/announce",
    "udp://open.tracker.cl:1337/announce",
    "udp://tracker.torrent.eu.org:451/announce",
    "udp://exodus.desync.com:6969/announce",
    "udp://open.stealth.si:80/announce",
]


def build_magnet(info_hash: str, name: str) -> str:
    s = f"magnet:?xt=urn:btih:{info_hash}&dn={quote_plus(name)}"
    return s + "".join(f"&tr={quote_plus(t)}" for t in _TRACKERS)


def human_size(n: int | float) -> str:
    if not n or n <= 0:
        return "?"
    units = ["B", "KB", "MB", "GB", "TB"]
    v, i = float(n), 0
    while v >= 1024 and i < len(units) - 1:
        v /= 1024
        i += 1
    return f"{v:.0f} {units[i]}" if (v >= 10 or i == 0) else f"{v:.1f} {units[i]}".replace(".", ",")


def merge_results(acc: list[Result]) -> list[Result]:
    """Un mismo torrent puede venir de varios motores: se queda uno por
    infoHash, recordando que lo dieron todos y quedándose de cada campo el que
    informa (un motor da el nombre del fichero y el otro solo su etiqueta)."""
    by_hash: dict[str, Result] = {}
    for r in acc:
        prev = by_hash.get(r.info_hash)
        if prev is None:
            by_hash[r.info_hash] = r
            continue
        base = r if r.seeders > prev.seeders else prev
        by_hash[r.info_hash] = base.copy(
            engine=merge_engines(prev.engine, r.engine),
            name=best_name(prev.name, r.name),
            size_bytes=max(prev.size_bytes, r.size_bytes),
            seeders=max(prev.seeders, r.seeders),
            quality=prev.quality if prev.quality != QUALITY_OTHER else r.quality,
            lang=prev.lang or r.lang,
            info=prev.info or r.info,
            pack=prev.pack or r.pack,
        )
    return list(by_hash.values())


def relevantes(items: list[Result], season: int | None, episode: int | None) -> list[Result]:
    """Deja fuera lo que NO es del episodio que se mira, y marca como pack lo
    que lo contiene (para que salga el selector de capítulos)."""
    if season is None or episode is None:
        return items
    out = []
    for r in items:
        fit = episode_fit(f"{r.name} {r.info}", season, episode)
        if fit is Fit.NO:
            continue
        out.append(r if (fit is Fit.OK or r.pack) else r.copy(pack=True))
    return out
